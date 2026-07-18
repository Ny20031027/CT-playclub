from rest_framework import serializers
from .models import (
    Order, OrderMember, OrderPrice, OrderComment, OrderRefund, OrderStatus
)


class OrderMemberSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    employee_avatar = serializers.SerializerMethodField()
    skill_name = serializers.CharField(source='skill.name', read_only=True)

    def get_employee_avatar(self, obj):
        if obj.employee and obj.employee.avatar:
            return obj.employee.avatar.url
        return ''

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
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    assigner_name = serializers.CharField(source='assigner.username', read_only=True)
    members = OrderMemberSerializer(many=True, read_only=True, source='order_members')
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    def get_customer_avatar(self, obj):
        if obj.customer and obj.customer.avatar:
            return obj.customer.avatar.url
        return ''

    class Meta:
        model = Order
        fields = ['id', 'order_no', 'customer', 'customer_name', 'customer_avatar',
                  'skill', 'skill_name', 'status', 'status_text', 'order_type',
                  'quantity', 'duration', 'unit_price', 'total_amount',
                  'discount_amount', 'pay_amount', 'pay_method', 'pay_time',
                  'start_time', 'end_time', 'assign_time', 'complete_time',
                  'cancel_time', 'cancel_reason', 'assigner', 'assigner_name',
                  'game_id', 'game_name', 'server', 'remark', 'customer_contact',
                  'platform', 'source', 'members', 'created_at', 'updated_at']
        read_only_fields = ['id', 'order_no', 'pay_time', 'start_time', 'end_time',
                            'assign_time', 'complete_time', 'cancel_time',
                            'created_at', 'updated_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    employee_ids = serializers.ListField(child=serializers.IntegerField(),
                                         write_only=True, required=False)

    class Meta:
        model = Order
        fields = ['id', 'order_no', 'customer', 'skill', 'order_type', 'quantity', 'duration',
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
