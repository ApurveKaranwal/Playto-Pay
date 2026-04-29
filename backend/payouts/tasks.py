import random
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .constants import (
    LEDGER_DEBIT,
    LEDGER_RELEASE,
    MAX_PAYOUT_RETRIES,
    PAYOUT_COMPLETED,
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_PROCESSING,
    PAYOUT_STUCK_AFTER_SECONDS,
)
from .models import LedgerEntry, Merchant, Payout
from .utils import can_transition


def _processing_deadline():
    return timezone.now() - timedelta(seconds=PAYOUT_STUCK_AFTER_SECONDS)


def _schedule_timeout_watch(payout_id, attempt):
    retry_stuck_payout.apply_async(
        args=[payout_id, attempt],
        countdown=PAYOUT_STUCK_AFTER_SECONDS,
    )


def _mark_terminal(payout, new_status, ledger_type):
    if not can_transition(payout.status, new_status):
        return False

    Merchant.objects.select_for_update().get(id=payout.merchant_id)
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        payout=payout,
        entry_type=ledger_type,
        amount_paise=payout.amount_paise,
        reference_id=str(payout.id),
    )
    payout.status = new_status
    payout.save(update_fields=["status", "updated_at"])
    return True


def _finalize_processing_attempt(payout_id):
    outcome = random.choices(["success", "fail", "hang"], weights=[70, 20, 10], k=1)[0]

    if outcome == "hang":
        return None

    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .filter(id=payout_id)
            .first()
        )
        if not payout or payout.status != PAYOUT_PROCESSING:
            return payout.status if payout else None

        ledger_type = LEDGER_DEBIT if outcome == "success" else LEDGER_RELEASE
        new_status = PAYOUT_COMPLETED if outcome == "success" else PAYOUT_FAILED
        _mark_terminal(payout, new_status, ledger_type)
        return new_status


@shared_task
def process_payout(payout_id):
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .filter(id=payout_id)
            .first()
        )
        if not payout or payout.status != PAYOUT_PENDING:
            return

        payout.status = PAYOUT_PROCESSING
        payout.attempts = 1
        payout.processing_started_at = timezone.now()
        payout.save(update_fields=["status", "attempts", "processing_started_at", "updated_at"])
        current_attempt = payout.attempts

    outcome = _finalize_processing_attempt(payout_id)
    if outcome is None:
        _schedule_timeout_watch(payout_id, current_attempt)


@shared_task
def retry_stuck_payout(payout_id, expected_attempt):
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .filter(id=payout_id)
            .first()
        )
        if not payout or payout.status != PAYOUT_PROCESSING:
            return
        if payout.attempts != expected_attempt:
            return
        if not payout.processing_started_at or payout.processing_started_at > _processing_deadline():
            return

        if payout.attempts >= MAX_PAYOUT_RETRIES:
            _mark_terminal(payout, PAYOUT_FAILED, LEDGER_RELEASE)
            return

        payout.attempts += 1
        payout.processing_started_at = timezone.now()
        payout.save(update_fields=["attempts", "processing_started_at", "updated_at"])
        current_attempt = payout.attempts

    delay_seconds = 2 ** (current_attempt - 1)
    finalize_retry_attempt.apply_async(args=[payout_id, current_attempt], countdown=delay_seconds)
    _schedule_timeout_watch(payout_id, current_attempt)


@shared_task
def finalize_retry_attempt(payout_id, expected_attempt):
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .filter(id=payout_id)
            .first()
        )
        if not payout or payout.status != PAYOUT_PROCESSING or payout.attempts != expected_attempt:
            return

    _finalize_processing_attempt(payout_id)
