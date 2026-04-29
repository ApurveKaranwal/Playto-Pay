from django.db.models import BigIntegerField, Case, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from .constants import (
    LEDGER_CREDIT,
    LEDGER_DEBIT,
    LEDGER_HOLD,
    PAYOUT_COMPLETED,
    PAYOUT_PENDING,
    PAYOUT_PROCESSING,
    VALID_TRANSITIONS,
)
from .models import LedgerEntry


def can_transition(current_status, next_status):
    return next_status in VALID_TRANSITIONS.get(current_status, set())


def ledger_balance_expression():
    # Available balance is status-aware:
    # pending/processing payouts reserve funds via HOLD,
    # completed payouts consume funds via DEBIT,
    # failed payouts net to zero because the HOLD is no longer active.
    active_hold_filter = Q(payout__status__in=[PAYOUT_PENDING, PAYOUT_PROCESSING]) | Q(payout__isnull=True)
    completed_debit_filter = Q(payout__status__isnull=True) | Q(payout__status=PAYOUT_COMPLETED)
    return Coalesce(
        Sum(
            Case(
                When(entry_type=LEDGER_CREDIT, then=F("amount_paise")),
                When(
                    Q(entry_type=LEDGER_DEBIT) & completed_debit_filter,
                    then=F("amount_paise") * Value(-1),
                ),
                When(
                    Q(entry_type=LEDGER_HOLD) & active_hold_filter,
                    then=F("amount_paise") * Value(-1),
                ),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        ),
        Value(0),
        output_field=BigIntegerField(),
    )


def merchant_balance_subquery():
    merchant_balances = (
        LedgerEntry.objects.filter(merchant_id=OuterRef("pk"))
        .values("merchant_id")
        .annotate(balance_paise=ledger_balance_expression())
        .values("balance_paise")[:1]
    )
    return Coalesce(
        Subquery(merchant_balances, output_field=BigIntegerField()),
        Value(0),
        output_field=BigIntegerField(),
    )


def get_merchant_balance(merchant_id):
    aggregation = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        balance_paise=ledger_balance_expression()
    )
    return aggregation["balance_paise"]
