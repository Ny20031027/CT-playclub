from rest_framework import serializers
from .models import (
    Config, Dictionary, DictionaryItem, OperationLog, ErrorLog
)
from apps.wx.models import Banner, Announcement


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = ['id', 'key', 'value', 'name', 'type', 'group', 'sort',
                  'remark', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DictionaryItemSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = DictionaryItem
        fields = ['id', 'dictionary', 'label', 'value', 'parent', 'sort',
                  'status', 'color', 'css_class', 'remark', 'children']
        read_only_fields = ['id', 'children']

    def get_children(self, obj):
        children = obj.children.filter(status=True, is_deleted=False).order_by('sort', 'id')
        return DictionaryItemSerializer(children, many=True).data


class DictionarySerializer(serializers.ModelSerializer):
    items = DictionaryItemSerializer(many=True, read_only=True)

    class Meta:
        model = Dictionary
        fields = ['id', 'name', 'code', 'type', 'sort', 'status',
                  'remark', 'items', 'created_at']
        read_only_fields = ['id', 'items', 'created_at']


class DictionarySimpleSerializer(serializers.ModelSerializer):
    item_list = serializers.SerializerMethodField()

    class Meta:
        model = Dictionary
        fields = ['id', 'name', 'code', 'type', 'item_list']
        read_only_fields = ['id', 'item_list']

    def get_item_list(self, obj):
        items = obj.items.filter(status=True, is_deleted=False).order_by('sort', 'id')
        return DictionaryItemSerializer(items, many=True).data


class OperationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = OperationLog
        fields = ['id', 'user', 'user_name', 'username', 'module', 'operation',
                  'method', 'path', 'ip', 'user_agent', 'params', 'result',
                  'status_code', 'duration', 'created_at']
        read_only_fields = ['id', 'created_at']


class ErrorLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ErrorLog
        fields = ['id', 'user', 'user_name', 'type', 'message', 'traceback',
                  'path', 'method', 'params', 'ip', 'created_at']
        read_only_fields = ['id', 'created_at']


class BannerManageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ['id', 'title', 'image', 'link_url', 'sort', 'status',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AnnouncementManageSerializer(serializers.ModelSerializer):
    type_text = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'type', 'type_text', 'sort',
                  'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
