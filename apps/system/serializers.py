from rest_framework import serializers
from .models import (
    Config, Dictionary, DictionaryItem, OperationLog, ErrorLog,
    CSWelcomeConfig, CSKeywordRule
)
from apps.wx.models import Banner, Announcement, GameBanner


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
        fields = ['id', 'title', 'content', 'image', 'type', 'type_text', 'sort',
                  'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CSWelcomeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSWelcomeConfig
        fields = ['id', 'welcome_text', 'is_enabled', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'welcome_text': {'required': False, 'allow_blank': True},
        }


class CSKeywordRuleSerializer(serializers.ModelSerializer):
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)

    class Meta:
        model = CSKeywordRule
        fields = ['id', 'keyword', 'reply_text', 'match_type', 'match_type_display',
                  'sort', 'is_enabled', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class GameBannerManageSerializer(serializers.ModelSerializer):
    game_name = serializers.CharField(source='game.name', read_only=True)

    class Meta:
        model = GameBanner
        fields = ['id', 'game', 'game_name', 'title', 'image', 'link_url', 'sort',
                  'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CouponSerializer(serializers.ModelSerializer):
    coupon_type_display = serializers.CharField(source='get_coupon_type_display', read_only=True)
    issued_count = serializers.SerializerMethodField()
    used_count = serializers.SerializerMethodField()

    class Meta:
        model = None  # runtime set
        fields = ['id', 'name', 'coupon_type', 'coupon_type_display', 'discount_rate',
                  'min_order_amount', 'max_discount_amount', 'is_enabled', 'description',
                  'issued_count', 'used_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_issued_count(self, obj):
        return obj.user_coupons.filter(is_deleted=False).count()

    def get_used_count(self, obj):
        return obj.user_coupons.filter(is_deleted=False, status='used').count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.Meta.model is None:
            from .models import Coupon
            self.Meta.model = Coupon


class UserCouponSerializer(serializers.ModelSerializer):
    coupon_name = serializers.CharField(source='coupon.name', read_only=True)
    coupon_type = serializers.CharField(source='coupon.coupon_type', read_only=True)
    discount_rate = serializers.SerializerMethodField()
    min_order_amount = serializers.SerializerMethodField()
    max_discount_amount = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)

    class Meta:
        model = None  # runtime set
        fields = ['id', 'customer', 'customer_name', 'coupon', 'coupon_name',
                  'coupon_type', 'discount_rate', 'min_order_amount',
                  'max_discount_amount', 'status', 'used_at', 'used_order_no',
                  'expire_time', 'operator', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_discount_rate(self, obj):
        return float(obj.coupon.discount_rate)

    def get_min_order_amount(self, obj):
        return float(obj.coupon.min_order_amount)

    def get_max_discount_amount(self, obj):
        return float(obj.coupon.max_discount_amount)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.Meta.model is None:
            from .models import UserCoupon
            self.Meta.model = UserCoupon


