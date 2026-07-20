from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny

from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import Customer, CustomerLevel, CustomerTag, Blacklist, CustomerConsumeRecord, CustomerService
from .serializers import (
    CustomerSerializer, CustomerLevelSerializer, CustomerTagSerializer,
    BlacklistSerializer, CustomerConsumeRecordSerializer, CustomerSimpleSerializer
)


class CustomerViewSet(BaseModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filterset_fields = ['level', 'gender', 'status', 'source']
    search_fields = ['nickname', 'phone', 'wechat', 'qq']
    ordering_fields = ['total_amount', 'total_orders', 'created_at', 'last_order_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        # 排除打手和客服身份的用户，确保每个用户只存在于一个列表
        return queryset.filter(
            cs_profile__isnull=True
        ).filter(
            Q(user__isnull=True) | (
                Q(user__employee__isnull=True) &
                Q(user__customer_service__isnull=True)
            )
        )

    @action(detail=False, methods=['get'], url_path='simple')
    def simple_list(self, request):
        customers = self.get_queryset().filter(status=True).order_by('-created_at')[:100]
        serializer = CustomerSimpleSerializer(customers, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='orders')
    def customer_orders(self, request, pk=None):
        from apps.order.models import Order
        from apps.order.serializers import OrderSerializer

        customer = self.get_object()
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = OrderSerializer(orders, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='consume-records')
    def consume_records(self, request, pk=None):
        customer = self.get_object()
        records = CustomerConsumeRecord.objects.filter(customer=customer).order_by('-created_at')
        page = self.paginate_queryset(records)
        if page is not None:
            serializer = CustomerConsumeRecordSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CustomerConsumeRecordSerializer(records, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='blacklist')
    def add_blacklist(self, request, pk=None):
        customer = self.get_object()
        reason = request.data.get('reason', '')
        expire_time = request.data.get('expire_time')
        Blacklist.objects.create(
            customer=customer,
            reason=reason,
            operator=request.user,
            expire_time=expire_time
        )
        customer.status = False
        customer.save(update_fields=['status'])
        return success_response(msg='已加入黑名单')

    @action(detail=True, methods=['post'], url_path='unblacklist')
    def remove_blacklist(self, request, pk=None):
        customer = self.get_object()
        Blacklist.objects.filter(customer=customer, status=True).update(status=False)
        customer.status = True
        customer.save(update_fields=['status'])
        return success_response(msg='已移出黑名单')

    @action(detail=True, methods=['post'], url_path='recharge')
    def recharge(self, request, pk=None):
        customer = self.get_object()
        amount = float(request.data.get('amount', 0) or 0)
        if amount <= 0:
            return success_response(code=400, msg='充值金额必须大于0')
        customer.balance += amount
        customer.save(update_fields=['balance'])
        CustomerConsumeRecord.objects.create(
            customer=customer,
            amount=amount,
            type='recharge',
            remark='充值',
        )
        return success_response(msg='充值成功')


class CustomerLevelViewSet(BaseModelViewSet):
    queryset = CustomerLevel.objects.all()
    serializer_class = CustomerLevelSerializer
    filterset_fields = ['status']
    search_fields = ['name']
    ordering_fields = ['level', 'sort']


class CustomerTagViewSet(BaseModelViewSet):
    queryset = CustomerTag.objects.all()
    serializer_class = CustomerTagSerializer
    filterset_fields = ['status']
    search_fields = ['name']
    ordering_fields = ['sort', 'id']


class BlacklistViewSet(BaseModelViewSet):
    queryset = Blacklist.objects.all()
    serializer_class = BlacklistSerializer
    filterset_fields = ['status', 'customer']
    search_fields = ['customer__nickname', 'reason']


class CustomerConsumeRecordViewSet(BaseModelViewSet):
    queryset = CustomerConsumeRecord.objects.all()
    serializer_class = CustomerConsumeRecordSerializer
    filterset_fields = ['type', 'customer']
    search_fields = ['order_no', 'customer__nickname']
    ordering_fields = ['amount', 'created_at']


@api_view(['GET'])
@permission_classes([AllowAny])
def cs_list(request):
    """客服列表"""
    keyword = request.GET.get('keyword', '')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # 排除打手和普通客户，确保每个用户只存在于一个列表
    queryset = CustomerService.objects.select_related('customer', 'customer__user').filter(
        Q(customer__user__isnull=True) | (
            Q(customer__user__employee__isnull=True) &
            Q(customer__user__customer__isnull=True)
        )
    )
    if keyword:
        queryset = queryset.filter(
            Q(customer__nickname__icontains=keyword) | Q(customer__phone__icontains=keyword)
        )

    total = queryset.count()
    start = (page - 1) * page_size
    records = queryset[start:start + page_size]

    data = []
    for record in records:
        data.append({
            'id': record.id,
            'customer_id': record.customer_id,
            'nickname': record.customer.nickname,
            'avatar': record.customer.avatar.url if record.customer.avatar else '',
            'phone': record.customer.phone,
            'status': record.status,
        })

    return success_response({
        'results': data,
        'total': total,
        'pages': (total + page_size - 1) // page_size,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def cs_add(request):
    """添加客服"""
    customer_id = request.data.get('customer_id')
    if not customer_id:
        return error_response(msg='请选择客户')

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return error_response(msg='客户不存在')

    if customer.user and hasattr(customer.user, 'employee'):
        return error_response(msg='该客户已经是打手，无法设置为客服')

    if CustomerService.objects.filter(customer=customer).exists():
        return error_response(msg='该客户已经是客服')

    CustomerService.objects.create(customer=customer, status='online')
    return success_response(msg='添加成功')


@api_view(['POST'])
@permission_classes([AllowAny])
def cs_remove(request, cs_id):
    """移除客服"""
    try:
        cs = CustomerService.objects.get(id=cs_id)
        cs.delete()
        return success_response(msg='移除成功')
    except CustomerService.DoesNotExist:
        return error_response(msg='客服不存在')
