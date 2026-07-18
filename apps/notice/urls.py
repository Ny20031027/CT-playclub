from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NoticeViewSet, UserNoticeViewSet, EmployeeNoticeViewSet,
    SmsLogViewSet, EmailLogViewSet
)

router = DefaultRouter()
router.register(r'notices', NoticeViewSet, basename='notice')
router.register(r'user-notices', UserNoticeViewSet, basename='user-notice')
router.register(r'employee-notices', EmployeeNoticeViewSet, basename='employee-notice')
router.register(r'sms-logs', SmsLogViewSet, basename='sms-log')
router.register(r'email-logs', EmailLogViewSet, basename='email-log')

urlpatterns = [
    path('', include(router.urls)),
]
