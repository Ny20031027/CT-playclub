from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import (
    Employee, EmployeeSkill, EmployeeWallet,
)
from apps.finance.models import Transaction, Wallet

from .models import Order, OrderMember
from .services import complete_order_and_settle, settle_order_commission


class OrderCommissionSettlementTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(username='settlement-customer')
        self.customer = Customer.objects.create(
            user=self.customer_user, nickname='结算客户'
        )
        self.skill = EmployeeSkill.objects.create(
            name='结算技能', category='test', status=True
        )

    def create_employee(self, suffix, employee_rate=None):
        user = User.objects.create_user(username=f'settlement-{suffix}')
        employee = Employee.objects.create(
            user=user,
            employee_no=f'SETTLE-{suffix}',
            real_name=f'打手{suffix}',
            nickname=f'打手{suffix}',
            status='busy',
            platform_commission_rate=(
                Decimal('100.00') - employee_rate
                if employee_rate is not None else Decimal('20.00')
            ),
        )
        return employee

    def create_order(self, order_no, pay_amount, employees, order_type='self_service'):
        order = Order.objects.create(
            order_no=order_no,
            customer=self.customer,
            skill=self.skill,
            status='in_progress',
            order_type=order_type,
            quantity=len(employees),
            duration=60,
            unit_price=pay_amount,
            total_amount=pay_amount,
            pay_amount=pay_amount,
        )
        for employee in employees:
            OrderMember.objects.create(
                order=order,
                employee=employee,
                skill=self.skill,
                unit_price=pay_amount,
                duration=60,
                amount=pay_amount / len(employees),
                status='in_progress',
            )
        return order

    def test_self_service_uses_employee_platform_rate_and_is_idempotent(self):
        employee = self.create_employee('one', Decimal('80.00'))
        order = self.create_order('SETTLE-ORDER-001', Decimal('100.00'), [employee])

        _, result = complete_order_and_settle(order.id)

        employee.refresh_from_db()
        member = order.order_members.get(employee=employee)
        self.assertEqual(result['commission_total'], Decimal('80.00'))
        self.assertEqual(member.commission_amount, Decimal('80.00'))
        self.assertEqual(employee.commission_balance, Decimal('80.00'))
        wallet = EmployeeWallet.objects.get(employee=employee)
        self.assertEqual(wallet.balance, Decimal('80.00'))
        self.assertEqual(wallet.total_income, Decimal('80.00'))
        self.assertEqual(employee.order_count, 1)
        self.assertEqual(employee.total_duration, 60)
        self.assertEqual(employee.status, 'idle')

        tx = Transaction.objects.get(
            order_no=order.order_no, employee=employee, category='order_settle'
        )
        self.assertEqual(tx.amount, Decimal('80.00'))
        self.assertEqual(tx.balance_after, Decimal('80.00'))
        platform_tx = Transaction.objects.get(
            order_no=order.order_no, employee=employee, category='platform_commission'
        )
        self.assertEqual(platform_tx.amount, Decimal('20.00'))
        self.assertEqual(Wallet.objects.get(type='platform').balance, Decimal('20.00'))

        order.refresh_from_db()
        repeated = settle_order_commission(order)
        employee.refresh_from_db()
        self.assertEqual(repeated['settled_count'], 0)
        self.assertEqual(employee.commission_balance, Decimal('80.00'))
        self.assertEqual(Transaction.objects.filter(order_no=order.order_no).count(), 2)
        self.assertEqual(Wallet.objects.get(type='platform').balance, Decimal('20.00'))

    def test_multi_member_commission_uses_each_employee_rate(self):
        first = self.create_employee('first', Decimal('60.00'))
        second = self.create_employee('second', Decimal('40.00'))
        order = self.create_order(
            'SETTLE-ORDER-002', Decimal('100.00'), [first, second], order_type='multi'
        )

        _, result = complete_order_and_settle(order.id)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(result['settled_count'], 2)
        self.assertEqual(result['commission_total'], Decimal('50.00'))
        self.assertEqual(result['platform_commission_total'], Decimal('50.00'))
        self.assertEqual(first.commission_balance, Decimal('30.00'))
        self.assertEqual(second.commission_balance, Decimal('20.00'))
        self.assertEqual(
            list(order.order_members.order_by('id').values_list('commission_amount', flat=True)),
            [Decimal('30.00'), Decimal('20.00')],
        )

    def test_multi_member_rounding_keeps_full_order_amount(self):
        employees = [
            self.create_employee(f'rounding-{index}', Decimal('100.00'))
            for index in range(3)
        ]
        order = self.create_order(
            'SETTLE-ORDER-ROUNDING', Decimal('10.00'), employees, order_type='multi'
        )

        _, result = complete_order_and_settle(order.id)

        commissions = list(
            order.order_members.order_by('id').values_list('commission_amount', flat=True)
        )
        self.assertEqual(commissions, [
            Decimal('3.34'), Decimal('3.33'), Decimal('3.33')
        ])
        self.assertEqual(result['commission_total'], Decimal('10.00'))

    def test_coupon_discount_does_not_reduce_employee_commission_base(self):
        employee = self.create_employee('coupon', Decimal('80.00'))
        order = self.create_order('SETTLE-ORDER-COUPON', Decimal('70.00'), [employee])
        order.total_amount = Decimal('100.00')
        order.discount_amount = Decimal('30.00')
        order.coupon_discount = Decimal('30.00')
        order.save(update_fields=['total_amount', 'discount_amount', 'coupon_discount'])

        _, result = complete_order_and_settle(order.id)

        employee.refresh_from_db()
        member = order.order_members.get(employee=employee)
        self.assertEqual(result['commission_total'], Decimal('80.00'))
        self.assertEqual(member.commission_amount, Decimal('80.00'))
        self.assertEqual(employee.commission_balance, Decimal('80.00'))
        self.assertEqual(
            Transaction.objects.get(
                order_no=order.order_no, employee=employee, category='platform_commission'
            ).amount,
            Decimal('20.00'),
        )

    def test_tip_is_settled_to_employee_without_platform_commission(self):
        employee = self.create_employee('tip', Decimal('80.00'))
        order = self.create_order('SETTLE-ORDER-TIP', Decimal('110.00'), [employee])
        order.total_amount = Decimal('100.00')
        order.tip_amount = Decimal('10.00')
        order.save(update_fields=['total_amount', 'tip_amount'])

        _, result = complete_order_and_settle(order.id)

        employee.refresh_from_db()
        member = order.order_members.get(employee=employee)
        self.assertEqual(result['commission_total'], Decimal('90.00'))
        self.assertEqual(result['platform_commission_total'], Decimal('20.00'))
        self.assertEqual(member.commission_amount, Decimal('90.00'))
        self.assertEqual(employee.commission_balance, Decimal('90.00'))
        self.assertEqual(
            Transaction.objects.get(
                order_no=order.order_no, employee=employee, category='platform_commission'
            ).amount,
            Decimal('20.00'),
        )

    def test_admin_complete_endpoint_also_settles_commission(self):
        employee = self.create_employee('admin', Decimal('70.00'))
        order = self.create_order('SETTLE-ORDER-003', Decimal('50.00'), [employee])
        client = APIClient()
        client.force_authenticate(user=self.customer_user)

        payload = client.post(
            f'/api/order/orders/{order.id}/complete/', {}, format='json'
        ).json()

        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['commission_total'], 35.0)
        self.assertEqual(payload['data']['platform_commission_total'], 15.0)
        employee.refresh_from_db()
        self.assertEqual(employee.commission_balance, Decimal('35.00'))

    def test_customer_end_endpoint_settles_commission(self):
        employee = self.create_employee('customer-end', Decimal('75.00'))
        order = self.create_order('SETTLE-ORDER-004', Decimal('40.00'), [employee])
        client = APIClient()
        client.force_authenticate(user=self.customer_user)

        payload = client.post(
            f'/api/wx/orders/{order.id}/end/', {}, format='json'
        ).json()

        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['commission_total'], 30.0)
        self.assertEqual(payload['data']['platform_commission_total'], 10.0)
        order.refresh_from_db()
        employee.refresh_from_db()
        self.assertEqual(order.status, 'completed')
        self.assertEqual(employee.commission_balance, Decimal('30.00'))
        self.assertTrue(Transaction.objects.filter(
            order_no=order.order_no,
            employee=employee,
            category='order_settle',
            amount=Decimal('30.00'),
        ).exists())
