from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from apps.common.response import success_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Config, Dictionary, DictionaryItem, OperationLog, ErrorLog
)
from .serializers import (
    ConfigSerializer, DictionarySerializer, DictionaryItemSerializer,
    OperationLogSerializer, ErrorLogSerializer, DictionarySimpleSerializer,
    BannerManageSerializer, AnnouncementManageSerializer
)
from apps.wx.models import Banner, Announcement


class ConfigViewSet(BaseModelViewSet):
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    filterset_fields = ['group', 'type']
    search_fields = ['key', 'name']
    ordering_fields = ['sort', 'key']

    @action(detail=False, methods=['get'], url_path='by-group')
    def by_group(self, request):
        group = request.query_params.get('group', 'basic')
        configs = self.get_queryset().filter(group=group).order_by('sort', 'key')
        data = {c.key: c.value for c in configs}
        return success_response(data)

    @action(detail=False, methods=['post'], url_path='batch-update')
    def batch_update(self, request):
        items = request.data.get('items', {})
        for key, value in items.items():
            Config.objects.filter(key=key).update(value=value)
        return success_response(msg='批量更新成功')


class DictionaryViewSet(BaseModelViewSet):
    queryset = Dictionary.objects.all()
    serializer_class = DictionarySerializer
    filterset_fields = ['type', 'status']
    search_fields = ['name', 'code']
    ordering_fields = ['sort', 'id']

    @action(detail=False, methods=['get'], url_path='by-code')
    def by_code(self, request):
        code = request.query_params.get('code', '')
        try:
            dictionary = Dictionary.objects.get(code=code, status=True)
            serializer = DictionarySimpleSerializer(dictionary)
            return success_response(serializer.data)
        except Dictionary.DoesNotExist:
            return success_response([])


class DictionaryItemViewSet(BaseModelViewSet):
    queryset = DictionaryItem.objects.all()
    serializer_class = DictionaryItemSerializer
    filterset_fields = ['dictionary', 'status', 'parent']
    search_fields = ['label', 'value']
    ordering_fields = ['sort', 'id']


class OperationLogViewSet(BaseModelViewSet):
    queryset = OperationLog.objects.all()
    serializer_class = OperationLogSerializer
    filterset_fields = ['method', 'status_code', 'user']
    search_fields = ['username', 'module', 'operation', 'path', 'ip']
    ordering_fields = ['created_at', 'duration']
    http_method_names = ['get', 'delete']


class ErrorLogViewSet(BaseModelViewSet):
    queryset = ErrorLog.objects.all()
    serializer_class = ErrorLogSerializer
    filterset_fields = ['type', 'method', 'user']
    search_fields = ['message', 'path', 'type', 'ip']
    ordering_fields = ['created_at']
    http_method_names = ['get', 'delete']

    @action(detail=False, methods=['post'], url_path='clear')
    def clear(self, request):
        days = int(request.data.get('days', 30))
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        ErrorLog.objects.filter(created_at__lt=cutoff).delete()
        return success_response(msg='清理完成')


class BannerManageViewSet(BaseModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = BannerManageSerializer
    filterset_fields = ['status']
    search_fields = ['title']
    ordering_fields = ['sort', 'created_at']


class AnnouncementManageViewSet(BaseModelViewSet):
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementManageSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['sort', 'created_at']
