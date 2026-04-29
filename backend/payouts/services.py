from django.db import IntegrityError, transaction
from django.http import Http404
from rest_framework import status

from .constants import LEDGER_CREDIT, LEDGER_HOLD, PAYOUT_PENDING
from .models import IdempotencyKey, LedgerEntry, Merchant, Payout
from .serializers import PayoutSerializer
from .tasks import process_payout
from .utils import get_merchant_balance, merchant_balance_subquery


class InsufficientBalanceError(Exception):
    pass


def get_stored_idempotent_response(merchant_id, key):
    stored = IdempotencyKey.objects.filter(merchant_id=merchant_id, key=key).first()
    if not stored:
        return None
    return stored.response_data, stored.response_status_code


def get_merchant_or_404(merchant_id):
    merchant = Merchant.objects.filter(id=merchant_id).first()
    if not merchant:
        raise Http404("Merchant not found")
    return merchant


def list_merchants():
    return Merchant.objects.annotate(balance_paise=merchant_balance_subquery()).order_by("id")


@transaction.atomic
def create_merchant(*, name):
    merchant = Merchant.objects.create(name=name)
    merchant.balance_paise = 0
    return merchant


@transaction.atomic
def create_credit(*, merchant_id, amount_paise, reference_id=""):
    merchant = Merchant.objects.select_for_update().filter(id=merchant_id).first()
    if not merchant:
        raise Http404("Merchant not found")

    entry = LedgerEntry.objects.create(
        merchant=merchant,
        entry_type=LEDGER_CREDIT,
        amount_paise=amount_paise,
        reference_id=reference_id,
    )

    return {
        "ledger_entry_id": entry.id,
        "merchant_id": merchant.id,
        "amount_paise": entry.amount_paise,
        "entry_type": entry.entry_type,
        "reference_id": entry.reference_id,
        "balance_paise": get_merchant_balance(merchant.id),
    }


def list_merchant_payouts(merchant_id):
    get_merchant_or_404(merchant_id)
    return Payout.objects.filter(merchant_id=merchant_id).order_by("-created_at", "-id")


def list_merchant_ledger(merchant_id):
    get_merchant_or_404(merchant_id)
    return (
        LedgerEntry.objects.filter(merchant_id=merchant_id)
        .select_related("payout")
        .order_by("-created_at", "-id")
    )


def get_merchant_balance_snapshot(merchant_id):
    merchant = get_merchant_or_404(merchant_id)
    return {
        "merchant_id": merchant.id,
        "balance_paise": get_merchant_balance(merchant.id),
    }


@transaction.atomic
def create_payout(*, merchant_id, amount_paise, bank_account_id, idempotency_key):
    merchant = Merchant.objects.select_for_update().filter(id=merchant_id).first()
    if not merchant:
        raise Http404("Merchant not found")

    stored_response = get_stored_idempotent_response(merchant.id, idempotency_key)
    if stored_response:
        return stored_response

    balance_paise = get_merchant_balance(merchant.id)
    if balance_paise < amount_paise:
        raise InsufficientBalanceError("Insufficient balance")

    payout = Payout.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        status=PAYOUT_PENDING,
        idempotency_key=idempotency_key,
        bank_account_id=bank_account_id,
    )

    LedgerEntry.objects.create(
        merchant=merchant,
        payout=payout,
        entry_type=LEDGER_HOLD,
        amount_paise=amount_paise,
        reference_id=str(payout.id),
    )

    response_data = PayoutSerializer(payout).data

    try:
        IdempotencyKey.objects.create(
            merchant=merchant,
            key=idempotency_key,
            payout=payout,
            response_status_code=status.HTTP_201_CREATED,
            response_data=response_data,
        )
    except IntegrityError:
        stored_response = get_stored_idempotent_response(merchant.id, idempotency_key)
        if stored_response:
            return stored_response
        raise

    transaction.on_commit(lambda: process_payout.delay(payout.id))
    return response_data, status.HTTP_201_CREATED
