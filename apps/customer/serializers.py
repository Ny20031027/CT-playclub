from rest_framework import serializers
from apps.account.models import User
from apps.account.serializers import validate_display_id
from apps.common.media import build_media_url
from .models import (
    Customer, CustomerLevel, CustomerTag, Blacklist, CustomerConsumeRecord,
    CustomerArchiveRecord
)


class CustomerLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerLevel
        fields = ['id', 'name', 'level', 'icon', 'min_amount', 'discount',
                  'color', 'sort', 'status', 'remark', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomerTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerTag
        fields = ['id', 'name', 'color', 'sort', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomerSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source='level.name', read_only=True)
    level_color = serializers.CharField(source='level.color', read_only=True)
    tag_names = serializers.SerializerMethodField()
    is_blacklisted = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    display_id = serializers.SerializerMethodField()
    edit_display_id = serializers.CharField(write_only=True, required=False)
    coins_frozen = serializers.BooleanField(read_only=True)
    user_banned = serializers.SerializerMethodField()
    ban_detail = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ['id', 'user', 'display_id', 'edit_display_id', 'nickname', 'avatar', 'avatar_url', 'phone', 'email', 'gender',
                  'age', 'wechat', 'qq', 'level', 'level_name', 'level_color',
                  'tags', 'tag_names', 'total_amount', 'total_orders', 'balance', 'coins',
                  'coins_frozen', 'user_banned', 'ban_detail',
                  'status', 'source', 'first_order_date', 'last_order_date',
                  'remark', 'address', 'is_blacklisted', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_amount', 'total_orders',
                            'first_order_date', 'last_order_date', 'created_at', 'updated_at']

    def get_tag_names(self, obj):
        return list(obj.tags.filter(status=True).values_list('name', flat=True))

    def get_is_blacklisted(self, obj):
        return obj.blacklist_records.filter(status=True, is_deleted=False).exists()

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))

    def get_display_id(self, obj):
        try:
            return obj.user.display_id
        except Exception:
            return ''

    def get_user_banned(self, obj):
        try:
            return bool(obj.user and obj.user.is_banned_active())
        except Exception:
            return False

    def get_ban_detail(self, obj):
        if not obj.user_id:
            return {'is_banned': False}
        from apps.account.ban_utils import ban_info
        return ban_info(obj.user)

    def validate_edit_display_id(self, value):
        value = validate_display_id(value)
        if not value:
            raise serializers.ValidationError('黑金ID不能为空')
        queryset = User.objects.filter(display_id=value)
        if self.instance and self.instance.user_id:
            queryset = queryset.exclude(pk=self.instance.user_id)
        if queryset.exists():
            raise serializers.ValidationError('该黑金ID已被其他用户使用')
        return value

    def create(self, validated_data):
        display_id_val = validated_data.pop('edit_display_id', None)
        tags = validated_data.pop('tags', [])
        customer = Customer.objects.create(**validated_data)
        if display_id_val and customer.user:
            customer.user.display_id = display_id_val
            customer.user.save(update_fields=['display_id'])
        if tags:
            customer.tags.set(tags)
        return customer

    def update(self, instance, validated_data):
        display_id_val = validated_data.pop('edit_display_id', None)
        tags = validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        if display_id_val and instance.user:
            instance.user.display_id = display_id_val
            instance.user.save(update_fields=['display_id'])
        return instance


class CustomerSimpleSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source='level.name', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ['id', 'nickname', 'avatar', 'avatar_url', 'level', 'level_name', 'phone']
        read_only_fields = fields

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))


class BlacklistSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = Blacklist
        fields = ['id', 'customer', 'customer_name', 'reason', 'operator',
                  'operator_name', 'expire_time', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomerConsumeRecordSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)

    class Meta:
        model = CustomerConsumeRecord
        fields = ['id', 'customer', 'customer_name', 'order_no', 'amount',
                  'type', 'remark', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomerArchiveRecordSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    priority_text = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = CustomerArchiveRecord
        fields = [
            'id', 'customer', 'customer_name', 'customer_phone', 'title',
            'category', 'priority', 'priority_text', 'content',
            'next_follow_time', 'operator', 'operator_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'operator', 'operator_name', 'created_at', 'updated_at']
