from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DailyStatViewSet, MonthlyStatViewSet, EmployeeRankViewSet,
    StatisticsViewSet
)

router = DefaultRouter()
router.register(r'daily', DailyStatViewSet, basename='daily-stat')
router.register(r'monthly', MonthlyStatViewSet, basename='monthly-stat')
router.register(r'employee-rank', EmployeeRankViewSet, basename='employee-rank-stat')
router.register(r'stats', StatisticsViewSet, basename='statistics')

urlpatterns = [
    path('', include(router.urls)),
]
