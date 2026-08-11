from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db import connection, DatabaseError
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Config, Dictionary, DictionaryItem, OperationLog, ErrorLog,
    CSWelcomeConfig, CSKeywordRule
)
from .serializers import (
    ConfigSerializer, DictionarySerializer, DictionaryItemSerializer,
    OperationLogSerializer, ErrorLogSerializer, DictionarySimpleSerializer,
    BannerManageSerializer, AnnouncementManageSerializer,
    CSWelcomeConfigSerializer, CSKeywordRuleSerializer,
    GameBannerManageSerializer
)
from apps.wx.models import Banner, Announcement, GameBanner


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
            obj, _ = Config.objects.get_or_create(
                key=key, defaults={'value': value, 'name': key}
            )
            obj.value = value
            obj.is_deleted = False
            obj.save(update_fields=['value', 'is_deleted', 'updated_at'])
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


class GameBannerManageViewSet(BaseModelViewSet):
    queryset = GameBanner.objects.all()
    serializer_class = GameBannerManageSerializer
    filterset_fields = ['game', 'status']
    search_fields = ['title']
    ordering_fields = ['sort', 'created_at']


def _table_exists(model):
    table_name = model._meta.db_table
    try:
        return table_name in connection.introspection.table_names()
    except Exception:
        return False


import logging as _logging
_cs_logger = _logging.getLogger('system')

_CS_TABLES_CREATED = False


def _ensure_column(table, column, col_def):
    """确保表中存在指定列，不存在则添加"""
    from django.db import connection
    try:
        cursor = connection.cursor()
        cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", [column])
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_def}")
            _cs_logger.info(f'自动加列成功: {table}.{column}')
        cursor.close()
    except Exception as e:
        _cs_logger.warning(f'自动加列失败 {table}.{column}: {e}')


_CS_CREATE_SQLS = [
    """CREATE TABLE IF NOT EXISTS `sys_cs_welcome_config` (
        `id` bigint NOT NULL AUTO_INCREMENT,
        `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
        `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
        `welcome_text` longtext NOT NULL DEFAULT '',
        `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci""",
    """CREATE TABLE IF NOT EXISTS `sys_cs_keyword_rule` (
        `id` bigint NOT NULL AUTO_INCREMENT,
        `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
        `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
        `keyword` varchar(200) NOT NULL,
        `reply_text` longtext NOT NULL,
        `match_type` varchar(20) NOT NULL DEFAULT 'contains',
        `sort` int NOT NULL DEFAULT 0,
        `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
        PRIMARY KEY (`id`),
        KEY `idx_keyword` (`keyword`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci""",
]


def _ensure_cs_tables():
    """Ensure customer-service config tables exist before request handlers write to them."""
    global _CS_TABLES_CREATED
    models = (CSWelcomeConfig, CSKeywordRule)
    if _CS_TABLES_CREATED and all(_table_exists(model) for model in models):
        return True

    try:
        existing_tables = set(connection.introspection.table_names())
        with connection.schema_editor() as schema_editor:
            for model in models:
                if model._meta.db_table not in existing_tables:
                    schema_editor.create_model(model)
                    existing_tables.add(model._meta.db_table)
        _CS_TABLES_CREATED = all(_table_exists(model) for model in models)
        if _CS_TABLES_CREATED:
            _cs_logger.info('Customer-service config tables are ready')
            return True
        _cs_logger.error('Customer-service config tables are still missing after auto create')
    except Exception as e:
        _cs_logger.warning(f'Customer-service schema editor create failed: {e}', exc_info=True)

    try:
        with connection.cursor() as cursor:
            for sql in _CS_CREATE_SQLS:
                cursor.execute(sql)
        _CS_TABLES_CREATED = all(_table_exists(model) for model in models)
        if _CS_TABLES_CREATED:
            _cs_logger.info('Customer-service config tables were created with fallback SQL')
            return True
        _cs_logger.error('Customer-service config tables are still missing after fallback SQL')
    except Exception as e:
        _cs_logger.error(f'Customer-service config table auto-create failed: {e}', exc_info=True)

    _CS_TABLES_CREATED = False
    return False


def _cs_tables_unavailable_response():
    return error_response(
        msg='客服配置表未初始化，自动创建失败；请先执行 python manage.py migrate，或导入 scripts/create_cs_tables.sql',
        code=500,
    )


class CSWelcomeConfigViewSet(BaseModelViewSet):
    queryset = CSWelcomeConfig.objects.none()
    serializer_class = CSWelcomeConfigSerializer
    http_method_names = ['get', 'post', 'put', 'patch']

    def get_queryset(self):
        if _table_exists(CSWelcomeConfig):
            return CSWelcomeConfig.objects.all()
        _ensure_cs_tables()
        if _table_exists(CSWelcomeConfig):
            return CSWelcomeConfig.objects.all()
        return CSWelcomeConfig.objects.none()

    def create(self, request, *args, **kwargs):
        if not _ensure_cs_tables():
            return _cs_tables_unavailable_response()
        try:
            return super().create(request, *args, **kwargs)
        except DatabaseError:
            if not _ensure_cs_tables():
                return _cs_tables_unavailable_response()
            return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _ensure_cs_tables():
            return _cs_tables_unavailable_response()
        try:
            return super().update(request, *args, **kwargs)
        except DatabaseError:
            if not _ensure_cs_tables():
                return _cs_tables_unavailable_response()
            return super().update(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """获取当前启用的欢迎语"""
        if not _table_exists(CSWelcomeConfig):
            _ensure_cs_tables()
        if not _table_exists(CSWelcomeConfig):
            return success_response({'welcome_text': '', 'is_enabled': False})
        config = CSWelcomeConfig.objects.filter(is_deleted=False, is_enabled=True).first()
        if config:
            return success_response({
                'id': config.id,
                'welcome_text': config.welcome_text,
                'is_enabled': config.is_enabled,
            })
        return success_response({'welcome_text': '', 'is_enabled': False})


class CSKeywordRuleViewSet(BaseModelViewSet):
    queryset = CSKeywordRule.objects.none()
    serializer_class = CSKeywordRuleSerializer
    filterset_fields = ['is_enabled', 'match_type']
    search_fields = ['keyword', 'reply_text']
    ordering_fields = ['sort', 'created_at']

    def get_queryset(self):
        if _table_exists(CSKeywordRule):
            return CSKeywordRule.objects.all()
        _ensure_cs_tables()
        if _table_exists(CSKeywordRule):
            return CSKeywordRule.objects.all()
        return CSKeywordRule.objects.none()

    def create(self, request, *args, **kwargs):
        if not _ensure_cs_tables():
            return _cs_tables_unavailable_response()
        try:
            return super().create(request, *args, **kwargs)
        except DatabaseError:
            if not _ensure_cs_tables():
                return _cs_tables_unavailable_response()
            return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _ensure_cs_tables():
            return _cs_tables_unavailable_response()
        try:
            return super().update(request, *args, **kwargs)
        except DatabaseError:
            if not _ensure_cs_tables():
                return _cs_tables_unavailable_response()
            return super().update(request, *args, **kwargs)


