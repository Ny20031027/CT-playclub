from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Wallet, Transaction, Settlement, SettlementDetail, Salary, Withdraw
)
from .serializers import (
    WalletSerializer, TransactionSerializer, SettlementSerializer,
    SettlementDetailSerializer, SalarySerializer, WithdrawSerializer
)


class WalletViewSet(BaseModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    filterset_fields = ['type']
    search_fields = ['user__username']


class TransactionViewSet(BaseModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    filterset_fields = ['type', 'category', 'employee', 'wallet']
    search_fields = ['transaction_no', 'order_no', 'remark']
    ordering_fields = ['amount', 'created_at']


class SettlementViewSet(BaseModelViewSet):
    queryset = Settlement.objects.all()
    serializer_class = SettlementSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['settlement_no']
    ordering_fields = ['total_amount', 'created_at']

    @action(detail=True, methods=['post'], url_path='process')
    def process(self, request, pk=None):
        settlement = self.get_object()
        if settlement.status != 'pending':
            return error_response(msg='结算单状态不正确')
        settlement.status = 'processing'
        settlement.save()
        from apps.employee.models import Employee
        from apps.order.models import Order, OrderMember, OrderStatus
        employees = Employee.objects.filter(is_deleted=False)
        start_date = settlement.start_date
        end_date = settlement.end_date
        total_amount = 0
        total_commission = 0
        order_count = 0
        for emp in employees:
            members = OrderMember.objects.filter(
                employee=emp,
                status='completed',
                created_at__gte=start_date,
                created_at__lte=end_date,
                is_deleted=False
            )
            emp_order_count = members.count()
            emp_total_amount = members.aggregate(sum=Sum('amount'))['sum'] or 0
            commission_rate = 50
            contract = emp.contracts.filter(status='active').first()
            if contract:
                commission_rate = contract.commission_rate
            commission = emp_total_amount * commission_rate / 100
            SettlementDetail.objects.create(
                settlement=settlement,
                employee=emp,
                order_count=emp_order_count,
                total_duration=0,
                total_amount=emp_total_amount,
                commission_amount=commission,
                commission_rate=commission_rate,
                status='completed'
            )
            total_amount += emp_total_amount
            total_commission += commission
            order_count += emp_order_count
        settlement.total_amount = total_amount
        settlement.total_commission = total_commission
        settlement.total_profit = total_amount - total_commission
        settlement.order_count = order_count
        settlement.status = 'completed'
        settlement.complete_time = timezone.now()
        settlement.operator = request.user
        settlement.save()
        return success_response(msg='结算完成')


class SettlementDetailViewSet(BaseModelViewSet):
    queryset = SettlementDetail.objects.all()
    serializer_class = SettlementDetailSerializer
    filterset_fields = ['settlement', 'employee', 'status']
    search_fields = ['employee__nickname']


class SalaryViewSet(BaseModelViewSet):
    queryset = Salary.objects.all()
    serializer_class = SalarySerializer
    filterset_fields = ['status', 'employee', 'month']
    search_fields = ['salary_no', 'employee__nickname']
    ordering_fields = ['total_amount', 'created_at']

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        salary = self.get_object()
        if salary.status != 'pending':
            return error_response(msg='工资单状态不正确')
        salary.status = 'paid'
        salary.pay_time = timezone.now()
        salary.operator = request.user
        salary.save()
        return success_response(msg='工资已发放')


class WithdrawViewSet(BaseModelViewSet):
    queryset = Withdraw.objects.all()
    serializer_class = WithdrawSerializer
    filterset_fields = ['status', 'withdraw_method', 'employee']
    search_fields = ['withdraw_no', 'employee__nickname']
    ordering_fields = ['amount', 'created_at']

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        withdraw = self.get_object()
        if withdraw.status != 'pending':
            return error_response(msg='提现申请状态不正确')
        withdraw.status = 'approved'
        withdraw.auditor = request.user
        withdraw.audit_time = timezone.now()
        withdraw.audit_remark = request.data.get('remark', '')
        withdraw.save()
        return success_response(msg='审核通过')

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        withdraw = self.get_object()
        if withdraw.status != 'pending':
            return error_response(msg='提现申请状态不正确')
        withdraw.status = 'rejected'
        withdraw.auditor = request.user
        withdraw.audit_time = timezone.now()
        withdraw.audit_remark = request.data.get('remark', '')
        withdraw.save()
        return success_response(msg='审核拒绝')

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        withdraw = self.get_object()
        if withdraw.status != 'approved':
            return error_response(msg='提现状态不正确')
        withdraw.status = 'completed'
        withdraw.complete_time = timezone.now()
        withdraw.save()
        from apps.employee.models import EmployeeWallet
        wallet = EmployeeWallet.objects.filter(employee=withdraw.employee).first()
        if wallet:
            wallet.balance -= withdraw.amount
            wallet.total_withdraw += withdraw.amount
            wallet.save()
        return success_response(msg='提现完成')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        from django.db.models import Count
        data = {
            'pending': Withdraw.objects.filter(status='pending', is_deleted=False).count(),
            'approved': Withdraw.objects.filter(status='approved', is_deleted=False).count(),
            'completed': Withdraw.objects.filter(status='completed', is_deleted=False).count(),
            'rejected': Withdraw.objects.filter(status='rejected', is_deleted=False).count(),
            'total_amount': Withdraw.objects.filter(status='completed', is_deleted=False).aggregate(sum=Sum('amount'))['sum'] or 0,
        }
        return success_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def finance_overview(request):
    """财务概览"""
    today = timezone.now().date()
    from datetime import timedelta
    month_start = today.replace(day=1)

    today_income = Transaction.objects.filter(
        type='income', created_at__date=today, is_deleted=False
    ).aggregate(sum=Sum('amount'))['sum'] or 0
    today_expense = Transaction.objects.filter(
        type='expense', created_at__date=today, is_deleted=False
    ).aggregate(sum=Sum('amount'))['sum'] or 0
    month_income = Transaction.objects.filter(
        type='income', created_at__gte=month_start, is_deleted=False
    ).aggregate(sum=Sum('amount'))['sum'] or 0
    month_expense = Transaction.objects.filter(
        type='expense', created_at__gte=month_start, is_deleted=False
    ).aggregate(sum=Sum('amount'))['sum'] or 0
    platform_wallet = Wallet.objects.filter(type='platform', is_deleted=False).first()
    balance = platform_wallet.balance if platform_wallet else 0
    pending_settlement = Settlement.objects.filter(
        status='pending', is_deleted=False
    ).aggregate(sum=Sum('total_amount'))['sum'] or 0

    data = {
        'todayIncome': float(today_income),
        'todayExpense': float(today_expense),
        'monthIncome': float(month_income),
        'monthExpense': float(month_expense),
        'balance': float(balance),
        'pendingSettlement': float(pending_settlement),
    }
    return success_response(data)
