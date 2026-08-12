from rest_framework import serializers
from apps.common.media import build_media_url
from .models import (
    Order, OrderMember, OrderPrice, OrderComment, OrderRefund, OrderStatus,
    SupportTicket
)


def get_related_user_display_id(obj):
    try:
        user = obj.user if obj else None
    except Exception:
        user = None
    return user.display_id if user else ''


class OrderMemberSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    employee_avatar = serializers.SerializerMethodField()
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    def get_employee_avatar(self, obj):
        return build_media_url(obj.employee.avatar if obj.employee else '', self.context.get('request'))

    class Meta:
        model = OrderMember
        fields = ['id', 'order', 'employee', 'employee_name', 'employee_avatar',
                  'skill', 'skill_name', 'unit_price', 'duration', 'amount',
                  'commission_amount', 'status', 'accept_time', 'start_time',
                  'end_time', 'remark']
        read_only_fields = ['id']


class OrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    customer_avatar = serializers.SerializerMethodField()
    customer_display_id = serializers.SerializerMethodField()
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    assigner_name = serializers.CharField(source='assigner.username', read_only=True)
    assigned_employee_id = serializers.SerializerMethodField()
    assigned_employee_name = serializers.SerializerMethodField()
    assigned_employee_avatar = serializers.SerializerMethodField()
    assigned_employee_display_id = serializers.SerializerMethodField()
    game_account_id = serializers.SerializerMethodField()
    game_account_name = serializers.SerializerMethodField()
    game_account_category = serializers.SerializerMethodField()
    members = OrderMemberSerializer(many=True, read_only=True, source='order_members')
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    def get_customer_avatar(self, obj):
        return build_media_url(obj.customer.avatar if obj.customer else '', self.context.get('request'))

    def get_customer_display_id(self, obj):
        return get_related_user_display_id(obj.customer)

    def get_assigned_employee_name(self, obj):
        if not obj.assigned_employee:
            return ''
        return obj.assigned_employee.nickname or obj.assigned_employee.real_name

    def get_assigned_employee_id(self, obj):
        return obj.assigned_employee_id

    def get_assigned_employee_avatar(self, obj):
        return build_media_url(
            obj.assigned_employee.avatar if obj.assigned_employee else '',
            self.context.get('request'),
        )

    def get_assigned_employee_display_id(self, obj):
        return get_related_user_display_id(obj.assigned_employee)

    def _snapshot_value(self, obj, key):
        snapshot = obj.self_service_snapshot or {}
        return snapshot.get(key) or ''

    def get_game_account_id(self, obj):
        return self._snapshot_value(obj, 'game_account_id')

    def get_game_account_name(self, obj):
        return self._snapshot_value(obj, 'game_account_name')

    def get_game_account_category(self, obj):
        return self._snapshot_value(obj, 'game_account_category')

    class Meta:
        model = Order
        fields = ['id', 'order_no', 'customer', 'customer_name', 'customer_avatar',
                  'customer_display_id', 'assigned_employee_id',
                  'assigned_employee_name', 'assigned_employee_avatar',
                  'assigned_employee_display_id', 'game_account_id',
                  'game_account_name', 'game_account_category',
                  'skill', 'skill_name', 'status', 'status_text', 'order_type',
                  'quantity', 'purchase_quantity', 'settlement_unit',
                  'self_service_snapshot', 'duration', 'unit_price', 'total_amount',
                  'discount_amount', 'pay_amount', 'pay_method', 'pay_time',
                  'start_time', 'end_time', 'assign_time', 'complete_time',
                  'cancel_time', 'cancel_reason', 'assigner', 'assigner_name',
                  'game_id', 'game_name', 'server', 'remark', 'customer_contact',
                  'platform', 'source', 'members', 'created_at', 'updated_at']
        read_only_fields = ['id', 'order_no', 'pay_time', 'start_time', 'end_time',
                            'assign_time', 'complete_time', 'cancel_time',
                            'self_service_snapshot', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField(),
                                         write_only=True, required=False)

    class Meta:
        model = Order
        fields = ['id', 'order_no', 'customer', 'skill', 'order_type', 'quantity',
                  'purchase_quantity', 'settlement_unit', 'duration',
                  'unit_price', 'total_amount', 'discount_amount', 'pay_amount',
                  'pay_method', 'game_id', 'game_name', 'server', 'remark',
                  'customer_contact', 'platform', 'source', 'employee_ids']
        read_only_fields = ['id', 'order_no']

    def create(self, validated_data):
        employee_ids = validated_data.pop('employee_ids', [])
        import datetime
        import uuid
        order_no = f"ORD{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        validated_data['order_no'] = order_no
        order = Order.objects.create(**validated_data)
        for emp_id in employee_ids:
            try:
                from apps.employee.models import Employee
                emp = Employee.objects.get(id=emp_id)
                unit_price = validated_data.get('unit_price', 0)
                duration = validated_data.get('duration', 0)
                amount = unit_price * duration / 60 if duration else 0
                OrderMember.objects.create(
                    order=order,
                    employee=emp,
                    skill=validated_data.get('skill'),
                    unit_price=unit_price,
                    duration=duration,
                    amount=amount,
                )
            except Exception:
                pass
        return order


class OrderPriceSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    class Meta:
        model = OrderPrice
        fields = ['id', 'skill', 'skill_name', 'level', 'unit_price',
                  'min_duration', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class OrderCommentSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = OrderComment
        fields = ['id', 'order', 'order_no', 'customer', 'customer_name',
                  'employee', 'employee_name', 'rating', 'content', 'tags',
                  'is_anonymous', 'images', 'reply', 'reply_time', 'created_at']
        read_only_fields = ['id', 'reply_time', 'created_at']


class OrderRefundSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    auditor_name = serializers.CharField(source='auditor.username', read_only=True)
    applicant_name = serializers.CharField(source='applicant.username', read_only=True)

    class Meta:
        model = OrderRefund
        fields = ['id', 'order', 'order_no', 'customer', 'customer_name',
                  'refund_no', 'refund_amount', 'refund_reason', 'refund_method',
                  'status', 'auditor', 'auditor_name', 'audit_remark',
                  'audit_time', 'complete_time', 'applicant', 'applicant_name',
                  'created_at']
        read_only_fields = ['id', 'refund_no', 'audit_time', 'complete_time', 'created_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['refund_no'] = f"REF{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class SupportTicketSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    handler_name = serializers.CharField(source='handler.username', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SupportTicket
        fields = ['id', 'ticket_no', 'order', 'order_no', 'customer', 'customer_name',
                  'employee', 'employee_name', 'title', 'description', 'status',
                  'status_text', 'order_snapshot', 'handler', 'handler_name',
                  'handle_remark', 'closed_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'ticket_no', 'order_snapshot', 'closed_at',
                            'created_at', 'updated_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['ticket_no'] = f"TK{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)
