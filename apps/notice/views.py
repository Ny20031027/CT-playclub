from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Notice, UserNotice, EmployeeNotice, SmsLog, EmailLog
)
from .serializers import (
    NoticeSerializer, UserNoticeSerializer, EmployeeNoticeSerializer,
    SmsLogSerializer, EmailLogSerializer
)


class NoticeViewSet(BaseModelViewSet):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    filterset_fields = ['type', 'level', 'is_published']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'publish_time']

    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        notice = self.get_object()
        notice.is_published = True
        notice.publish_time = timezone.now()
        notice.save()
        return success_response(msg='发布成功')

    @action(detail=True, methods=['post'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        notice = self.get_object()
        notice.is_published = False
        notice.save()
        return success_response(msg='撤回成功')


class UserNoticeViewSet(BaseModelViewSet):
    queryset = UserNotice.objects.all()
    serializer_class = UserNoticeSerializer
    filterset_fields = ['is_read', 'notice__type']
    search_fields = ['notice__title']
    ordering_fields = ['created_at']

    @action(detail=False, methods=['get'], url_path='my')
    def my_notices(self, request):
        notices = self.get_queryset().filter(user=request.user).order_by('-created_at')
        page = self.paginate_queryset(notices)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(notices, many=True)
        return success_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(user=request.user, is_read=False).count()
        return success_response({'unread_count': count})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        self.get_queryset().filter(user=request.user, is_read=False).update(
            is_read=True, read_time=timezone.now()
        )
        return success_response(msg='全部已读')

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notice = self.get_object()
        notice.is_read = True
        notice.read_time = timezone.now()
        notice.save()
        return success_response(msg='已读')


class EmployeeNoticeViewSet(BaseModelViewSet):
    queryset = EmployeeNotice.objects.all()
    serializer_class = EmployeeNoticeSerializer
    filterset_fields = ['is_read', 'notice__type', 'employee']
    search_fields = ['notice__title', 'employee__nickname']
    ordering_fields = ['created_at']

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        employee_id = request.data.get('employee')
        if not employee_id:
            return error_response(msg='缺少employee参数')
        self.get_queryset().filter(employee_id=employee_id, is_read=False).update(
            is_read=True, read_time=timezone.now()
        )
        return success_response(msg='全部已读')


class SmsLogViewSet(BaseModelViewSet):
    queryset = SmsLog.objects.all()
    serializer_class = SmsLogSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['phone', 'content']
    ordering_fields = ['created_at', 'send_time']

    @action(detail=True, methods=['post'], url_path='retry')
    def retry(self, request, pk=None):
        sms = self.get_object()
        sms.status = 'pending'
        sms.save()
        return success_response(msg='已加入发送队列')


class EmailLogViewSet(BaseModelViewSet):
    queryset = EmailLog.objects.all()
    serializer_class = EmailLogSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['email', 'subject']
    ordering_fields = ['created_at', 'send_time']
