from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.employee.models import Employee, EmployeeWallet
from apps.finance.models import Transaction, Wallet

from .models import Order, OrderStatus


MONEY_STEP = Decimal('0.01')
DEFAULT_PLATFORM_COMMISSION_RATE = Decimal('20.00')


class OrderCompletionError(Exception):
    """订单无法完成时抛出的业务异常。"""


def _money(value):
    return Decimal(str(value or 0)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _platform_commission_rate(employee):
    rate = _money(
        employee.platform_commission_rate
        if employee.platform_commission_rate is not None
        else DEFAULT_PLATFORM_COMMISSION_RATE
    )
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
        return {
            'settled_count': 0,
            'commission_total': Decimal('0.00'),
            'platform_commission_total': Decimal('0.00'),
        }

    gross_total = max(_money(locked_order.pay_amount), Decimal('0.00'))
    gross_shares = _split_evenly(gross_total, len(members))
    settled_count = 0
    commission_total = Decimal('0.00')
    platform_commission_total = Decimal('0.00')
    platform_wallet = Wallet.objects.select_for_update().filter(
        type='platform', is_deleted=False
    ).order_by('id').first()
    if platform_wallet is None:
        platform_wallet = Wallet.objects.create(type='platform')

    for member, gross_share in zip(members, gross_shares):
        employee_tx_exists = Transaction.objects.filter(
            order_no=locked_order.order_no,
            employee_id=member.employee_id,
            category='order_settle',
        ).exists()
        platform_tx_exists = Transaction.objects.filter(
            order_no=locked_order.order_no,
            employee_id=member.employee_id,
            category='platform_commission',
        ).exists()

        employee = Employee.objects.select_for_update().get(pk=member.employee_id)
        platform_rate = _platform_commission_rate(employee)
        employee_rate = Decimal('100.00') - platform_rate
        employee_commission = (gross_share * employee_rate / Decimal('100')).quantize(
            MONEY_STEP, rounding=ROUND_HALF_UP
        )
        platform_commission = gross_share - employee_commission
        if member.commission_amount != employee_commission:
            member.commission_amount = employee_commission
            member.save(update_fields=['commission_amount', 'updated_at'])

        if not employee_tx_exists:
            employee.commission_balance = (
                _money(employee.commission_balance) + employee_commission
            )
            employee.save(update_fields=['commission_balance', 'updated_at'])

            employee_wallet, _ = EmployeeWallet.objects.select_for_update().get_or_create(
                employee=employee
            )
            employee_wallet.balance = _money(employee_wallet.balance) + employee_commission
            employee_wallet.total_income = (
                _money(employee_wallet.total_income) + employee_commission
            )
            employee_wallet.save(update_fields=['balance', 'total_income', 'updated_at'])

            Transaction.objects.create(
                employee=employee,
                order_no=locked_order.order_no,
                transaction_no=f'OSC{locked_order.id:010d}{member.id:010d}',
                type='income',
                category='order_settle',
                amount=employee_commission,
                balance_after=employee.commission_balance,
                remark=(
                    f'订单 {locked_order.order_no} 打手结算：订单分摊¥{gross_share} × '
                    f'{employee_rate}%（平台抽成{platform_rate}%）'
                ),
                source='order',
            )
            settled_count += 1
            commission_total += employee_commission

        if not platform_tx_exists:
            platform_wallet.balance = _money(platform_wallet.balance) + platform_commission
            platform_wallet.total_income = (
                _money(platform_wallet.total_income) + platform_commission
            )
            platform_wallet.save(update_fields=['balance', 'total_income', 'updated_at'])
            Transaction.objects.create(
                wallet=platform_wallet,
                employee=employee,
                order_no=locked_order.order_no,
                transaction_no=f'OPC{locked_order.id:010d}{member.id:010d}',
                type='income',
                category='platform_commission',
                amount=platform_commission,
                balance_after=platform_wallet.balance,
                remark=(
                    f'订单 {locked_order.order_no} 平台抽成：订单分摊¥{gross_share} × '
                    f'{platform_rate}%'
                ),
                source='order',
            )
            platform_commission_total += platform_commission

    return {
        'settled_count': settled_count,
        'commission_total': _money(commission_total),
        'platform_commission_total': _money(platform_commission_total),
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
