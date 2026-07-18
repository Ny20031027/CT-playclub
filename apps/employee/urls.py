from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmployeeViewSet, EmployeeSkillViewSet, EmployeeTagViewSet,
    EmployeeWalletViewSet, EmployeeContractViewSet, EmployeeStatusViewSet
)

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'skills', EmployeeSkillViewSet, basename='employee-skill')
router.register(r'tags', EmployeeTagViewSet, basename='employee-tag')
router.register(r'wallets', EmployeeWalletViewSet, basename='employee-wallet')
router.register(r'contracts', EmployeeContractViewSet, basename='employee-contract')
router.register(r'statuses', EmployeeStatusViewSet, basename='employee-status')

urlpatterns = [
    path('', include(router.urls)),
]
