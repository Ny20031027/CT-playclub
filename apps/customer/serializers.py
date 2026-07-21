from rest_framework import serializers
from apps.common.media import build_media_url
from .models import (
    Customer, CustomerLevel, CustomerTag, Blacklist, CustomerConsumeRecord
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

    class Meta:
        model = Customer
        fields = ['id', 'user', 'nickname', 'avatar', 'avatar_url', 'phone', 'email', 'gender',
                  'age', 'wechat', 'qq', 'level', 'level_name', 'level_color',
                  'tags', 'tag_names', 'total_amount', 'total_orders', 'balance',
                  'status', 'source', 'first_order_date', 'last_order_date',
                  'remark', 'address', 'is_blacklisted', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_amount', 'total_orders', 'balance',
                            'first_order_date', 'last_order_date', 'created_at', 'updated_at']

    def get_tag_names(self, obj):
        return list(obj.tags.filter(status=True).values_list('name', flat=True))

    def get_is_blacklisted(self, obj):
        return obj.blacklist_records.filter(status=True, is_deleted=False).exists()

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))

    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        customer = Customer.objects.create(**validated_data)
        if tags:
            customer.tags.set(tags)
        return customer

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
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
