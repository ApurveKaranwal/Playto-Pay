from rest_framework import serializers

from .models import LedgerEntry, Merchant, Payout


class CreatePayoutSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField(min_value=1)
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)


class MerchantSerializer(serializers.ModelSerializer):
    balance_paise = serializers.IntegerField(read_only=True)

    class Meta:
        model = Merchant
        fields = ["id", "name", "balance_paise", "created_at"]


class CreateMerchantSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class CreateCreditSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField(min_value=1)
    amount_paise = serializers.IntegerField(min_value=1)
    reference_id = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id",
            "merchant_id",
            "amount_paise",
            "status",
            "idempotency_key",
            "bank_account_id",
            "attempts",
            "processing_started_at",
            "created_at",
            "updated_at",
        ]


class MerchantBalanceSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField()
    balance_paise = serializers.IntegerField()


class LedgerEntrySerializer(serializers.ModelSerializer):
    payout_status = serializers.CharField(source="payout.status", read_only=True, allow_null=True)

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "merchant_id",
            "payout_id",
            "payout_status",
            "entry_type",
            "amount_paise",
            "reference_id",
            "created_at",
        ]
