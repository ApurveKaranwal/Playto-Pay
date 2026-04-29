import threading
import uuid
from unittest.mock import patch

from rest_framework.test import APIClient
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings

from .constants import LEDGER_CREDIT, LEDGER_HOLD
from .models import IdempotencyKey, LedgerEntry, Merchant, Payout
from .services import InsufficientBalanceError, create_payout
from .tasks import process_payout
from .utils import get_merchant_balance


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class IdempotencyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(name="Merchant A")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LEDGER_CREDIT,
            amount_paise=10000,
            reference_id="seed-credit",
        )

    @patch("payouts.services.process_payout.delay")
    def test_same_request_returns_same_response_and_single_record(self, mocked_delay):
        payload = {
            "merchant_id": self.merchant.id,
            "amount_paise": 6000,
            "bank_account_id": "bank-1",
            "idempotency_key": str(uuid.uuid4()),
        }

        with self.captureOnCommitCallbacks(execute=True):
            first_response, first_status = create_payout(**payload)
            second_response, second_status = create_payout(**payload)

        self.assertEqual(first_status, 201)
        self.assertEqual(first_response, second_response)
        self.assertEqual(second_status, 201)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(IdempotencyKey.objects.count(), 1)
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LEDGER_HOLD, merchant=self.merchant).count(),
            1,
        )
        mocked_delay.assert_called_once()

    @patch("payouts.services.process_payout.delay")
    def test_balance_and_payouts_endpoints_match_contract(self, mocked_delay):
        payload = {
            "merchant_id": self.merchant.id,
            "amount_paise": 3000,
            "bank_account_id": "bank-2",
        }

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/payouts",
                data=payload,
                format="json",
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        self.assertEqual(response.status_code, 201)

        balance_response = self.client.get(f"/api/v1/merchants/{self.merchant.id}/balance")
        payouts_response = self.client.get(f"/api/v1/merchants/{self.merchant.id}/payouts")

        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.json()["balance_paise"], 7000)
        self.assertEqual(payouts_response.status_code, 200)
        self.assertEqual(len(payouts_response.json()), 1)
        self.assertEqual(payouts_response.json()[0]["merchant_id"], self.merchant.id)
        mocked_delay.assert_called_once()

    def test_merchant_creation_credit_and_ledger_endpoints(self):
        merchant_response = self.client.post(
            "/api/v1/merchants",
            data={"name": "Merchant D"},
            format="json",
        )

        self.assertEqual(merchant_response.status_code, 201)
        merchant_id = merchant_response.json()["id"]
        self.assertEqual(merchant_response.json()["balance_paise"], 0)

        credit_response = self.client.post(
            "/api/v1/credits",
            data={
                "merchant_id": merchant_id,
                "amount_paise": 2500,
                "reference_id": "manual-topup",
            },
            format="json",
        )

        self.assertEqual(credit_response.status_code, 201)
        self.assertEqual(credit_response.json()["balance_paise"], 2500)

        merchants_response = self.client.get("/api/v1/merchants")
        balance_response = self.client.get(f"/api/v1/merchants/{merchant_id}/balance")
        ledger_response = self.client.get(f"/api/v1/merchants/{merchant_id}/ledger")

        self.assertEqual(merchants_response.status_code, 200)
        self.assertTrue(any(item["id"] == merchant_id for item in merchants_response.json()))
        self.assertEqual(balance_response.status_code, 200)
        self.assertEqual(balance_response.json()["balance_paise"], 2500)
        self.assertEqual(ledger_response.status_code, 200)
        self.assertEqual(len(ledger_response.json()), 1)
        self.assertEqual(ledger_response.json()[0]["entry_type"], LEDGER_CREDIT)

    def test_create_payout_requires_idempotency_header(self):
        response = self.client.post(
            "/api/v1/payouts",
            data={
                "merchant_id": self.merchant.id,
                "amount_paise": 1000,
                "bank_account_id": "bank-3",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Missing Idempotency-Key header")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class PayoutTaskTests(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(name="Merchant C")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LEDGER_CREDIT,
            amount_paise=10000,
            reference_id="seed-credit",
        )

    def _create_pending_payout(self):
        payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=4000,
            status="pending",
            idempotency_key=str(uuid.uuid4()),
            bank_account_id="bank-task",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            payout=payout,
            entry_type=LEDGER_HOLD,
            amount_paise=4000,
            reference_id=str(payout.id),
        )
        return payout

    @patch("payouts.tasks.random.choices", return_value=["success"])
    def test_process_payout_success_creates_debit_and_completes(self, mocked_choices):
        payout = self._create_pending_payout()

        process_payout(payout.id)
        payout.refresh_from_db()

        self.assertEqual(payout.status, "completed")
        self.assertEqual(payout.attempts, 1)
        self.assertTrue(
            LedgerEntry.objects.filter(payout=payout, entry_type="DEBIT", amount_paise=4000).exists()
        )
        self.assertEqual(get_merchant_balance(self.merchant.id), 6000)
        mocked_choices.assert_called_once()

    @patch("payouts.tasks.random.choices", return_value=["fail"])
    def test_process_payout_failure_creates_release_and_fails(self, mocked_choices):
        payout = self._create_pending_payout()

        process_payout(payout.id)
        payout.refresh_from_db()

        self.assertEqual(payout.status, "failed")
        self.assertEqual(payout.attempts, 1)
        self.assertTrue(
            LedgerEntry.objects.filter(payout=payout, entry_type="RELEASE", amount_paise=4000).exists()
        )
        self.assertEqual(get_merchant_balance(self.merchant.id), 10000)
        mocked_choices.assert_called_once()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(name="Merchant B")
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LEDGER_CREDIT,
            amount_paise=10000,
            reference_id="seed-credit",
        )

    def _attempt_create(self, idempotency_key, results):
        close_old_connections()
        try:
            response, response_status = create_payout(
                merchant_id=self.merchant.id,
                amount_paise=6000,
                bank_account_id="bank-1",
                idempotency_key=idempotency_key,
            )
            results.append(("success", response_status, response))
        except InsufficientBalanceError as exc:
            results.append(("error", str(exc)))
        finally:
            close_old_connections()

    @patch("payouts.services.process_payout.delay")
    def test_two_simultaneous_requests_only_allow_one_payout(self, mocked_delay):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrency locking semantics require PostgreSQL for this test.")

        results = []
        threads = [
            threading.Thread(target=self._attempt_create, args=(str(uuid.uuid4()), results))
            for _ in range(2)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        successes = [item for item in results if item[0] == "success"]
        errors = [item for item in results if item[0] == "error"]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(get_merchant_balance(self.merchant.id), 4000)
        mocked_delay.assert_called_once()
