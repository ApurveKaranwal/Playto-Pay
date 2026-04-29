from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    CreateCreditSerializer,
    CreateMerchantSerializer,
    CreatePayoutSerializer,
    LedgerEntrySerializer,
    MerchantBalanceSerializer,
    MerchantSerializer,
    PayoutSerializer,
)
from .services import (
    InsufficientBalanceError,
    create_credit,
    create_merchant,
    create_payout,
    get_merchant_balance_snapshot,
    list_merchant_ledger,
    list_merchants,
    list_merchant_payouts,
)


class MerchantListCreateView(APIView):
    def get(self, request):
        queryset = list_merchants()
        return Response(MerchantSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = CreateMerchantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = create_merchant(name=serializer.validated_data["name"])
        return Response(MerchantSerializer(merchant).data, status=status.HTTP_201_CREATED)


class CreateCreditView(APIView):
    def post(self, request):
        serializer = CreateCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = create_credit(**serializer.validated_data)
        except Http404 as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(payload, status=status.HTTP_201_CREATED)


class CreatePayoutView(APIView):
    def post(self, request):
        serializer = CreatePayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response({"error": "Missing Idempotency-Key header"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            response_data, response_status = create_payout(
                merchant_id=serializer.validated_data["merchant_id"],
                amount_paise=serializer.validated_data["amount_paise"],
                bank_account_id=serializer.validated_data["bank_account_id"],
                idempotency_key=idempotency_key,
            )
        except Http404 as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except InsufficientBalanceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(response_data, status=response_status)


class MerchantBalanceView(APIView):
    def get(self, request, merchant_id):
        try:
            payload = get_merchant_balance_snapshot(merchant_id)
        except Http404 as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(MerchantBalanceSerializer(payload).data)


class MerchantPayoutListView(APIView):
    def get(self, request, merchant_id):
        try:
            queryset = list_merchant_payouts(merchant_id)
        except Http404 as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(PayoutSerializer(queryset, many=True).data)


class MerchantLedgerListView(APIView):
    def get(self, request, merchant_id):
        try:
            queryset = list_merchant_ledger(merchant_id)
        except Http404 as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(LedgerEntrySerializer(queryset, many=True).data)
