from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WalletViewSet, TransactionViewSet, SettlementViewSet,
    SettlementDetailViewSet, SalaryViewSet, WithdrawViewSet,
    finance_overview
)

router = DefaultRouter()
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'settlements', SettlementViewSet, basename='settlement')
router.register(r'settlement-details', SettlementDetailViewSet, basename='settlement-detail')
router.register(r'salaries', SalaryViewSet, basename='salary')
router.register(r'withdraws', WithdrawViewSet, basename='withdraw')

urlpatterns = [
    path('overview/', finance_overview),
    path('', include(router.urls)),
]
