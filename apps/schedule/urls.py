from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ShiftViewSet, ScheduleViewSet, LeaveViewSet,
    AttendanceViewSet, BookingViewSet, cs_schedule_list, cs_schedule_delete
)

router = DefaultRouter()
router.register(r'shifts', ShiftViewSet, basename='shift')
router.register(r'schedules', ScheduleViewSet, basename='schedule')
router.register(r'leaves', LeaveViewSet, basename='leave')
router.register(r'attendances', AttendanceViewSet, basename='attendance')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('', include(router.urls)),
    path('cs-schedules/', cs_schedule_list, name='cs-schedule-list'),
    path('cs-schedules/<int:schedule_id>/', cs_schedule_delete, name='cs-schedule-delete'),
]
