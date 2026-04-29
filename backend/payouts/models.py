from django.core.validators import MinValueValidator
from django.db import models

from .constants import (
    LEDGER_CREDIT,
    LEDGER_DEBIT,
    LEDGER_HOLD,
    LEDGER_RELEASE,
    PAYOUT_COMPLETED,
    PAYOUT_FAILED,
    PAYOUT_PENDING,
    PAYOUT_PROCESSING,
)


class Merchant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Payout(models.Model):
    STATUS_CHOICES = [
        (PAYOUT_PENDING, "Pending"),
        (PAYOUT_PROCESSING, "Processing"),
        (PAYOUT_COMPLETED, "Completed"),
        (PAYOUT_FAILED, "Failed"),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="payouts")
    amount_paise = models.BigIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PAYOUT_PENDING)
    idempotency_key = models.CharField(max_length=255)
    bank_account_id = models.CharField(max_length=255)
    attempts = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "idempotency_key"],
                name="uniq_payout_idempotency_per_merchant",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="payout_amount_paise_gt_zero",
            ),
        ]
        ordering = ["-created_at", "-id"]


class LedgerEntry(models.Model):
    TYPE_CHOICES = [
        (LEDGER_CREDIT, "Credit"),
        (LEDGER_HOLD, "Hold"),
        (LEDGER_DEBIT, "Debit"),
        (LEDGER_RELEASE, "Release"),
    ]

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="ledger_entries")
    payout = models.ForeignKey(
        Payout,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount_paise = models.BigIntegerField(validators=[MinValueValidator(1)])
    reference_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_paise__gt=0),
                name="ledger_amount_paise_gt_zero",
            ),
        ]
        indexes = [
            models.Index(
                fields=["merchant", "entry_type", "created_at"],
                name="payouts_led_merchan_f45ca4_idx",
            ),
            models.Index(
                fields=["payout", "entry_type"],
                name="payouts_led_payout__db246f_idx",
            ),
        ]
        ordering = ["created_at", "id"]


class IdempotencyKey(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="idempotency_keys")
    key = models.CharField(max_length=255)
    response_status_code = models.PositiveSmallIntegerField()
    response_data = models.JSONField()
    payout = models.OneToOneField(
        Payout,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="idempotency_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "key"],
                name="uniq_idempotency_key_per_merchant",
            ),
        ]
