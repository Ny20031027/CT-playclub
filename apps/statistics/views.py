from django.db.models import Sum, Count
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.common.response import success_response
from apps.common.media import build_media_url
from apps.common.viewsets import BaseModelViewSet
from .models import DailyStat, MonthlyStat, EmployeeRank
from .serializers import DailyStatSerializer, MonthlyStatSerializer, EmployeeRankSerializer
from apps.order.models import Order, OrderStatus
from apps.customer.models import Customer
from apps.employee.models import Employee


class DailyStatViewSet(BaseModelViewSet):
    queryset = DailyStat.objects.all()
    serializer_class = DailyStatSerializer
    filterset_fields = []
    ordering_fields = ['date']
    search_fields = []


class MonthlyStatViewSet(BaseModelViewSet):
    queryset = MonthlyStat.objects.all()
    serializer_class = MonthlyStatSerializer
    filterset_fields = ['year', 'month']
    ordering_fields = ['year', 'month']


class EmployeeRankViewSet(BaseModelViewSet):
    queryset = EmployeeRank.objects.all()
    serializer_class = EmployeeRankSerializer
    filterset_fields = ['period', 'date']
    search_fields = ['employee__nickname']
    ordering_fields = ['rank', 'order_count', 'total_amount']


class StatisticsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        today = timezone.now().date()
        today_orders = Order.objects.filter(created_at__date=today, is_deleted=False).count()
        today_amount = Order.objects.filter(
            created_at__date=today,
            status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
            is_deleted=False,
        ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
        total_orders = Order.objects.filter(is_deleted=False).count()
        total_amount = Order.objects.filter(
            status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
            is_deleted=False,
        ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
        total_customers = Customer.objects.filter(
            is_deleted=False,
            cs_profile__isnull=True,
        ).filter(
            Q(user__isnull=True) | Q(user__employee__isnull=True)
        ).distinct().count()
        total_employees = Employee.objects.filter(is_deleted=False).count()
        active_employees = Employee.objects.filter(
            status__in=['idle', 'busy'],
            is_deleted=False,
        ).count()
        return success_response({
            'today_orders': today_orders,
            'today_amount': today_amount,
            'total_orders': total_orders,
            'total_amount': total_amount,
            'total_customers': total_customers,
            'total_employees': total_employees,
            'active_employees': active_employees,
        })

    @action(detail=False, methods=['get'], url_path='trend')
    def trend(self, request):
        period = request.query_params.get('period', 'week')
        days = 7 if period == 'week' else 30
        from datetime import timedelta

        today = timezone.now().date()
        date_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
        order_data = []
        amount_data = []
        for date_item in date_list:
            day_orders = Order.objects.filter(created_at__date=date_item, is_deleted=False).count()
            day_amount = Order.objects.filter(
                created_at__date=date_item,
                status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
                is_deleted=False,
            ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
            order_data.append(day_orders)
            amount_data.append(float(day_amount))
        return success_response({
            'dates': [d.strftime('%Y-%m-%d') for d in date_list],
            'orders': order_data,
            'amounts': amount_data,
        })

    @action(detail=False, methods=['get'], url_path='employee-rank')
    def employee_rank(self, request):
        period = request.query_params.get('period', 'month')
        limit = int(request.query_params.get('limit', 10))
        from datetime import timedelta

        today = timezone.now().date()
        if period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'month':
            start_date = today - timedelta(days=30)
        else:
            start_date = today - timedelta(days=365)

        from apps.order.models import OrderMember

        rank_list = OrderMember.objects.filter(
            status='completed',
            created_at__gte=start_date,
            is_deleted=False,
        ).values('employee').annotate(
            order_count=Count('id'),
            total_duration=Sum('duration'),
            total_amount=Sum('amount'),
        ).order_by('-total_amount')[:limit]

        result = []
        for idx, item in enumerate(rank_list, 1):
            emp = Employee.objects.filter(id=item['employee']).first()
            if emp:
                result.append({
                    'rank': idx,
                    'employee_id': emp.id,
                    'employee_name': emp.nickname,
                    'employee_avatar': build_media_url(emp.avatar, request),
                    'order_count': item['order_count'],
                    'total_duration': item['total_duration'] or 0,
                    'total_amount': float(item['total_amount'] or 0),
                })
        return success_response(result)

    @action(detail=False, methods=['get'], url_path='order-status')
    def order_status(self, request):
        status_data = Order.objects.filter(is_deleted=False).values('status').annotate(count=Count('id'))
        return success_response({item['status']: item['count'] for item in status_data})

    @action(detail=False, methods=['get'], url_path='finance-overview')
    def finance_overview(self, request):
        today = timezone.now().date()
        today_income = Order.objects.filter(
            created_at__date=today,
            status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
            is_deleted=False,
        ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
        month_start = today.replace(day=1)
        month_income = Order.objects.filter(
            created_at__gte=month_start,
            status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
            is_deleted=False,
        ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
        from apps.finance.models import Withdraw

        month_withdraw = Withdraw.objects.filter(
            created_at__gte=month_start,
            status='completed',
            is_deleted=False,
        ).aggregate(sum=Sum('amount'))['sum'] or 0
        total_income = Order.objects.filter(
            status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
            is_deleted=False,
        ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
        return success_response({
            'today_income': float(today_income),
            'month_income': float(month_income),
            'month_withdraw': float(month_withdraw),
            'month_profit': float(month_income) - float(month_withdraw),
            'total_income': float(total_income),
        })
