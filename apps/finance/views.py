from decimal import Decimal

from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from apps.employee.models import Employee, EmployeeWallet
from apps.order.models import Order, OrderStatus
from .models import (
    Wallet, Transaction, Settlement, SettlementDetail, Salary, Withdraw, Recharge
)
from .serializers import (
    WalletSerializer, TransactionSerializer, SettlementSerializer,
    SettlementDetailSerializer, SalarySerializer, WithdrawSerializer, RechargeSerializer
)


class WalletViewSet(BaseModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    filterset_fields = ['type']
    search_fields = ['user__username']


class TransactionViewSet(BaseModelViewSet):
    queryset = Transaction.objects.select_related('wallet', 'employee', 'operator').all()
    serializer_class = TransactionSerializer
    filterset_fields = ['type', 'category', 'employee', 'wallet']
    search_fields = ['transaction_no', 'order_no', 'remark', 'employee__nickname']
    ordering_fields = ['amount', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        scope = self.request.query_params.get('scope')
        if scope == 'platform':
            queryset = queryset.filter(
                Q(category='platform_commission') | Q(wallet__type='platform')
            )
        elif scope == 'employee':
            queryset = queryset.filter(employee__isnull=False).exclude(
                category='platform_commission'
            )
        return queryset


class SettlementViewSet(BaseModelViewSet):
    queryset = Settlement.objects.all()
    serializer_class = SettlementSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['settlement_no']
    ordering_fields = ['total_amount', 'created_at']

    @action(detail=True, methods=['post'], url_path='process')
    @transaction.atomic
    def process(self, request, pk=None):
        settlement = Settlement.objects.select_for_update().get(pk=pk, is_deleted=False)
        if settlement.status != 'pending':
            return error_response(msg='结算单状态不正确')
        if not settlement.start_date or not settlement.end_date:
            return error_response(msg='请先设置结算开始和结束日期')
        if settlement.start_date > settlement.end_date:
            return error_response(msg='结算开始日期不能晚于结束日期')
        settlement.status = 'processing'
        settlement.save(update_fields=['status', 'updated_at'])
        from apps.order.models import OrderMember

        employees = Employee.objects.filter(is_deleted=False)
        start_date = settlement.start_date
        end_date = settlement.end_date
        total_amount = Decimal('0.00')
        total_commission = Decimal('0.00')
        order_count = 0
        for emp in employees:
            members = OrderMember.objects.filter(
                employee=emp,
                status='completed',
                order__complete_time__date__gte=start_date,
                order__complete_time__date__lte=end_date,
                order__status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
                is_deleted=False,
            )
            emp_order_count = members.count()
            if not emp_order_count:
                continue
            totals = members.aggregate(
                amount=Sum('amount'),
                commission=Sum('commission_amount'),
                duration=Sum('duration'),
            )
            emp_total_amount = totals['amount'] or Decimal('0.00')
            commission = totals['commission'] or Decimal('0.00')
            commission_rate = Decimal('100.00') - emp.platform_commission_rate
            SettlementDetail.objects.create(
                settlement=settlement,
                employee=emp,
                order_count=emp_order_count,
                total_duration=totals['duration'] or 0,
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
        settlement.save(update_fields=[
            'total_amount', 'total_commission', 'total_profit', 'order_count',
            'status', 'complete_time', 'operator', 'updated_at',
        ])
        return success_response(data={
            'order_count': order_count,
            'total_amount': float(total_amount),
            'employee_commission': float(total_commission),
            'platform_income': float(total_amount - total_commission),
        }, msg='结算完成')


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
    queryset = Withdraw.objects.select_related('employee', 'auditor').all()
    serializer_class = WithdrawSerializer
    filterset_fields = ['status', 'withdraw_method', 'employee']
    search_fields = ['withdraw_no', 'employee__nickname']
    ordering_fields = ['amount', 'created_at']

    @transaction.atomic
    def perform_create(self, serializer):
        employee = serializer.validated_data['employee']
        amount = serializer.validated_data['amount']
        fee = serializer.validated_data.get('fee', Decimal('0.00'))
        if amount <= 0:
            raise serializers.ValidationError({'amount': '提现金额必须大于0'})
        if fee < 0 or fee > amount:
            raise serializers.ValidationError({'fee': '手续费不能小于0或超过提现金额'})
        wallet, _ = EmployeeWallet.objects.select_for_update().get_or_create(
            employee=employee
        )
        available = wallet.balance - wallet.frozen_amount
        if amount > available:
            raise serializers.ValidationError({
                'amount': f'可提现余额不足，当前可用¥{available}'
            })
        wallet.frozen_amount += amount
        wallet.save(update_fields=['frozen_amount', 'updated_at'])
        serializer.save(actual_amount=amount - fee)

    @action(detail=True, methods=['post'], url_path='approve')
    @transaction.atomic
    def approve(self, request, pk=None):
        withdraw = Withdraw.objects.select_for_update().get(pk=pk, is_deleted=False)
        if withdraw.status != 'pending':
            return error_response(msg='提现申请状态不正确')
        withdraw.status = 'approved'
        withdraw.auditor = request.user
        withdraw.audit_time = timezone.now()
        withdraw.audit_remark = request.data.get('remark', '')
        withdraw.save()
        return success_response(msg='审核通过')

    @action(detail=True, methods=['post'], url_path='reject')
    @transaction.atomic
    def reject(self, request, pk=None):
        withdraw = Withdraw.objects.select_for_update().get(pk=pk, is_deleted=False)
        if withdraw.status != 'pending':
            return error_response(msg='提现申请状态不正确')
        withdraw.status = 'rejected'
        withdraw.auditor = request.user
        withdraw.audit_time = timezone.now()
        withdraw.audit_remark = request.data.get('remark', '')
        withdraw.save()
        wallet = EmployeeWallet.objects.select_for_update().filter(
            employee=withdraw.employee
        ).first()
        if wallet:
            wallet.frozen_amount = max(
                Decimal('0.00'), wallet.frozen_amount - withdraw.amount
            )
            wallet.save(update_fields=['frozen_amount', 'updated_at'])
        return success_response(msg='审核拒绝')

    @action(detail=True, methods=['post'], url_path='complete')
    @transaction.atomic
    def complete(self, request, pk=None):
        withdraw = Withdraw.objects.select_for_update().get(pk=pk, is_deleted=False)
        if withdraw.status != 'approved':
            return error_response(msg='提现状态不正确')
        wallet = EmployeeWallet.objects.select_for_update().filter(
            employee=withdraw.employee
        ).first()
        if not wallet or wallet.balance < withdraw.amount:
            return error_response(msg='打手钱包余额不足，无法完成提现')
        withdraw.status = 'completed'
        withdraw.complete_time = timezone.now()
        withdraw.save()
        wallet.balance -= withdraw.amount
        wallet.frozen_amount = max(
            Decimal('0.00'), wallet.frozen_amount - withdraw.amount
        )
        wallet.total_withdraw += withdraw.amount
        wallet.save(update_fields=[
            'balance', 'frozen_amount', 'total_withdraw', 'updated_at'
        ])
        employee = Employee.objects.select_for_update().get(pk=withdraw.employee_id)
        employee.commission_balance = max(
            Decimal('0.00'), employee.commission_balance - withdraw.amount
        )
        employee.save(update_fields=['commission_balance', 'updated_at'])
        Transaction.objects.create(
            employee=employee,
            order_no='',
            transaction_no=f'WD{withdraw.id:018d}',
            type='expense',
            category='employee_withdraw',
            amount=withdraw.amount,
            balance_after=wallet.balance,
            remark=f'提现单 {withdraw.withdraw_no} 完成打款',
            operator=request.user,
            source='withdraw',
        )
        return success_response(data={
            'balance': float(wallet.balance),
            'actual_amount': float(withdraw.actual_amount),
        }, msg='提现完成')

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
    month_start = today.replace(day=1)

    completed_orders = Order.objects.filter(
        status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED], is_deleted=False
    )
    platform_transactions = Transaction.objects.filter(
        category='platform_commission', is_deleted=False
    )
    employee_transactions = Transaction.objects.filter(
        category='order_settle', is_deleted=False
    )
    completed_withdraws = Withdraw.objects.filter(
        status='completed', is_deleted=False
    )
    pending_withdraws = Withdraw.objects.filter(
        status__in=['pending', 'approved', 'processing'], is_deleted=False
    )
    completed_recharges = Recharge.objects.filter(
        status='completed', is_deleted=False
    )

    order_revenue = completed_orders.aggregate(total=Sum('pay_amount'))['total'] or 0
    platform_income = platform_transactions.aggregate(total=Sum('amount'))['total'] or 0
    employee_commission = employee_transactions.aggregate(total=Sum('amount'))['total'] or 0
    completed_withdraw = completed_withdraws.aggregate(total=Sum('amount'))['total'] or 0
    pending_withdraw = pending_withdraws.aggregate(total=Sum('amount'))['total'] or 0
    recharge_total = completed_recharges.aggregate(total=Sum('amount'))['total'] or 0
    today_platform_income = platform_transactions.filter(
        created_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    month_platform_income = platform_transactions.filter(
        created_at__date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    month_employee_commission = employee_transactions.filter(
        created_at__date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or 0
    platform_wallet = Wallet.objects.filter(type='platform', is_deleted=False).first()
    balance = platform_wallet.balance if platform_wallet else 0
    employee_wallet_balance = EmployeeWallet.objects.filter(
        is_deleted=False
    ).aggregate(total=Sum('balance'))['total'] or 0

    data = {
        'orderRevenue': float(order_revenue),
        'platformIncome': float(platform_income),
        'employeeCommission': float(employee_commission),
        'completedWithdraw': float(completed_withdraw),
        'pendingWithdraw': float(pending_withdraw),
        'rechargeTotal': float(recharge_total),
        'employeeWalletBalance': float(employee_wallet_balance),
        'settledOrderCount': completed_orders.count(),
        'todayPlatformIncome': float(today_platform_income),
        'monthPlatformIncome': float(month_platform_income),
        'monthEmployeeCommission': float(month_employee_commission),
        # 兼容旧版财务页面字段。
        'todayIncome': float(today_platform_income),
        'todayExpense': 0.0,
        'monthIncome': float(month_platform_income),
        'monthExpense': float(month_employee_commission),
        'balance': float(balance),
        'pendingSettlement': float(pending_withdraw),
    }
    return success_response(data)


class RechargeViewSet(BaseModelViewSet):
    queryset = Recharge.objects.all()
    serializer_class = RechargeSerializer
    filterset_fields = ['status', 'payment_method', 'customer']
    search_fields = ['recharge_no', 'customer__nickname']
    ordering_fields = ['amount', 'created_at']

    @action(detail=False, methods=['get'], url_path='customer-recharges')
    def customer_recharges(self, request):
        """获取指定客户的充值记录"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return error_response(msg='请指定客户ID')
        
        queryset = self.get_queryset().filter(customer_id=customer_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """取消充值记录"""
        recharge = self.get_object()
        if recharge.status != 'pending':
            return error_response(msg='只有待完成的充值记录才能取消')
        recharge.status = 'cancelled'
        recharge.save()
        return success_response(msg='已取消')

    @transaction.atomic
    def perform_create(self, serializer):
        """创建充值记录时，同时更新客户余额和黑钻"""
        from apps.customer.models import Customer

        customer = Customer.objects.select_for_update().get(
            pk=serializer.validated_data['customer'].pk
        )
        instance = serializer.save(customer=customer, operator=self.request.user)
        # 更新客户余额和黑钻
        if instance.status == 'completed':
            customer.balance += instance.amount
            customer.coins += instance.coins
            customer.save(update_fields=['balance', 'coins'])
