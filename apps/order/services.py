from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.employee.models import Employee, EmployeeContract, EmployeeWallet
from apps.finance.models import Transaction

from .models import Order, OrderStatus


MONEY_STEP = Decimal('0.01')
DEFAULT_COMMISSION_RATE = Decimal('50.00')


class OrderCompletionError(Exception):
    """订单无法完成时抛出的业务异常。"""


def _money(value):
    return Decimal(str(value or 0)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _commission_rate(employee, completed_at):
    completed_date = completed_at.date()
    contract = EmployeeContract.objects.filter(
        employee=employee,
        status='active',
        is_deleted=False,
        start_date__lte=completed_date,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=completed_date)
    ).order_by('-start_date', '-id').first()
    rate = _money(contract.commission_rate if contract else DEFAULT_COMMISSION_RATE)
    return min(max(rate, Decimal('0.00')), Decimal('100.00'))


def _split_evenly(total, count):
    """按分拆分金额，确保多人订单各份相加仍等于订单实付金额。"""
    total_cents = int((_money(total) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    base_cents, remainder = divmod(total_cents, count)
    return [
        Decimal(base_cents + (1 if index < remainder else 0)) / Decimal('100')
        for index in range(count)
    ]


@transaction.atomic
def settle_order_commission(order):
    """给已完成订单的所有有效打手结算佣金，支持重复调用和断点补偿。"""
    locked_order = Order.objects.select_for_update().get(pk=order.pk)
    if locked_order.status not in [OrderStatus.COMPLETED, OrderStatus.REVIEWED]:
        raise OrderCompletionError('订单尚未完成，无法结算佣金')

    members = list(
        locked_order.order_members.select_for_update()
        .filter(is_deleted=False, employee__isnull=False, status='completed')
        .select_related('employee')
        .order_by('id')
    )
    if not members:
        return {'settled_count': 0, 'commission_total': Decimal('0.00')}

    gross_total = max(_money(locked_order.pay_amount), Decimal('0.00'))
    gross_shares = _split_evenly(gross_total, len(members))
    completed_at = locked_order.complete_time or timezone.now()
    settled_count = 0
    commission_total = Decimal('0.00')

    for member, gross_share in zip(members, gross_shares):
        # 老数据可能只完成了一部分结算，因此按“订单 + 打手”逐人判断。
        if Transaction.objects.filter(
            order_no=locked_order.order_no,
            employee_id=member.employee_id,
            category='order_settle',
        ).exists():
            continue

        employee = Employee.objects.select_for_update().get(pk=member.employee_id)
        rate = _commission_rate(employee, completed_at)
        commission = (gross_share * rate / Decimal('100')).quantize(
            MONEY_STEP, rounding=ROUND_HALF_UP
        )
        member.commission_amount = commission
        member.save(update_fields=['commission_amount', 'updated_at'])

        employee.commission_balance = _money(employee.commission_balance) + commission
        employee.save(update_fields=['commission_balance', 'updated_at'])

        employee_wallet, _ = EmployeeWallet.objects.select_for_update().get_or_create(
            employee=employee
        )
        employee_wallet.balance = _money(employee_wallet.balance) + commission
        employee_wallet.total_income = _money(employee_wallet.total_income) + commission
        employee_wallet.save(update_fields=['balance', 'total_income', 'updated_at'])

        Transaction.objects.create(
            employee=employee,
            order_no=locked_order.order_no,
            transaction_no=f'OSC{locked_order.id:010d}{member.id:010d}',
            type='income',
            category='order_settle',
            amount=commission,
            balance_after=employee.commission_balance,
            remark=(
                f'订单 {locked_order.order_no} 佣金结算：'
                f'订单分摊¥{gross_share} × {rate}%'
            ),
            source='order',
        )
        settled_count += 1
        commission_total += commission

    return {
        'settled_count': settled_count,
        'commission_total': _money(commission_total),
    }


@transaction.atomic
def complete_order_and_settle(order_id, completed_at=None):
    """原子完成订单、释放打手状态、更新统计并结算佣金。"""
    completed_at = completed_at or timezone.now()
    order = Order.objects.select_for_update().get(pk=order_id, is_deleted=False)
    if order.status != OrderStatus.IN_PROGRESS:
        raise OrderCompletionError('订单不存在或状态不正确')

    order.status = OrderStatus.COMPLETED
    order.end_time = completed_at
    order.complete_time = completed_at
    order.save(update_fields=['status', 'end_time', 'complete_time', 'updated_at'])

    members = list(
        order.order_members.select_for_update()
        .filter(is_deleted=False, employee__isnull=False)
        .order_by('id')
    )
    employee_durations = {}
    for member in members:
        member.status = 'completed'
        member.end_time = completed_at
        member.save(update_fields=['status', 'end_time', 'updated_at'])
        employee_durations.setdefault(
            member.employee_id, member.duration or order.duration or 0
        )

    for employee_id, duration in employee_durations.items():
        employee = Employee.objects.select_for_update().get(pk=employee_id)
        employee.status = 'idle'
        employee.order_count = (employee.order_count or 0) + 1
        employee.total_duration = (employee.total_duration or 0) + duration
        employee.save(update_fields=[
            'status', 'order_count', 'total_duration', 'updated_at'
        ])

    settlement = settle_order_commission(order)
    return order, settlement
