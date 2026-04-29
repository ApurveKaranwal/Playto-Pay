from django.urls import path

from payouts.views import (
    CreateCreditView,
    CreatePayoutView,
    MerchantBalanceView,
    MerchantLedgerListView,
    MerchantListCreateView,
    MerchantPayoutListView,
)


urlpatterns = [
    path("api/v1/merchants", MerchantListCreateView.as_view(), name="merchant-list-create"),
    path("api/v1/credits", CreateCreditView.as_view(), name="create-credit"),
    path("api/v1/payouts", CreatePayoutView.as_view(), name="create-payout"),
    path(
        "api/v1/merchants/<int:merchant_id>/balance",
        MerchantBalanceView.as_view(),
        name="merchant-balance",
    ),
    path(
        "api/v1/merchants/<int:merchant_id>/payouts",
        MerchantPayoutListView.as_view(),
        name="merchant-payouts",
    ),
    path(
        "api/v1/merchants/<int:merchant_id>/ledger",
        MerchantLedgerListView.as_view(),
        name="merchant-ledger",
    ),
]
