from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill, EmployeeWallet
from apps.employee.serializers import EmployeeSerializer
from apps.order.models import Order, OrderMember
from apps.order.services import complete_order_and_settle

from .models import Transaction, Wallet, Withdraw


class FinanceFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='finance-admin')
        self.customer = Customer.objects.create(user=self.user, nickname='财务客户')
        employee_user = User.objects.create_user(username='finance-employee')
        self.employee = Employee.objects.create(
            user=employee_user,
            employee_no='FIN-EMP-001',
            nickname='财务打手',
            real_name='财务打手',
            platform_commission_rate=Decimal('20.00'),
            commission_balance=Decimal('100.00'),
        )
        self.wallet = EmployeeWallet.objects.create(
            employee=self.employee,
            balance=Decimal('100.00'),
            total_income=Decimal('100.00'),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_withdraw_freezes_then_completes_and_creates_employee_flow(self):
        created = self.client.post('/api/finance/withdraws/', {
            'employee': self.employee.id,
            'amount': 60,
            'fee': 5,
            'withdraw_method': 'alipay',
            'account_name': '财务打手',
            'account_no': 'account-001',
        }, format='json').json()
        self.assertEqual(created['code'], 200)
        withdraw = Withdraw.objects.get(pk=created['data']['id'])
        self.wallet.refresh_from_db()
        self.assertEqual(withdraw.actual_amount, Decimal('55.00'))
        self.assertEqual(self.wallet.frozen_amount, Decimal('60.00'))

        approved = self.client.post(
            f'/api/finance/withdraws/{withdraw.id}/approve/', {}, format='json'
        ).json()
        self.assertEqual(approved['code'], 200)
        completed = self.client.post(
            f'/api/finance/withdraws/{withdraw.id}/complete/', {}, format='json'
        ).json()
        self.assertEqual(completed['code'], 200)

        self.wallet.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('40.00'))
        self.assertEqual(self.wallet.frozen_amount, Decimal('0.00'))
        self.assertEqual(self.employee.commission_balance, Decimal('40.00'))
        self.assertTrue(Transaction.objects.filter(
            employee=self.employee,
            category='employee_withdraw',
            type='expense',
            amount=Decimal('60.00'),
        ).exists())

    def test_rejected_withdraw_releases_frozen_balance(self):
        created = self.client.post('/api/finance/withdraws/', {
            'employee': self.employee.id,
            'amount': 30,
            'withdraw_method': 'wechat',
        }, format='json').json()
        withdraw_id = created['data']['id']

        rejected = self.client.post(
            f'/api/finance/withdraws/{withdraw_id}/reject/', {}, format='json'
        ).json()

        self.assertEqual(rejected['code'], 200)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100.00'))
        self.assertEqual(self.wallet.frozen_amount, Decimal('0.00'))

    def test_platform_and_employee_flows_are_separate(self):
        skill = EmployeeSkill.objects.create(name='财务测试技能', category='test')
        order = Order.objects.create(
            order_no='FIN-ORDER-001', customer=self.customer, skill=skill,
            status='in_progress', order_type='self_service', quantity=1,
            duration=60, total_amount=Decimal('100.00'),
            pay_amount=Decimal('100.00'), unit_price=Decimal('100.00'),
        )
        OrderMember.objects.create(
            order=order, employee=self.employee, skill=skill,
            status='in_progress', duration=60, amount=Decimal('100.00'),
        )

        complete_order_and_settle(order.id)

        platform = self.client.get('/api/finance/transactions/', {
            'scope': 'platform', 'page_size': 20,
        }).json()['data']['results']
        employee = self.client.get('/api/finance/transactions/', {
            'scope': 'employee', 'page_size': 20,
        }).json()['data']['results']
        overview = self.client.get('/api/finance/overview/').json()['data']

        self.assertEqual([item['category'] for item in platform], ['platform_commission'])
        self.assertEqual([item['category'] for item in employee], ['order_settle'])
        self.assertEqual(Decimal(platform[0]['amount']), Decimal('20.00'))
        self.assertEqual(Decimal(employee[0]['amount']), Decimal('80.00'))
        self.assertEqual(overview['platformIncome'], 20.0)
        self.assertEqual(overview['employeeCommission'], 80.0)
        self.assertEqual(Wallet.objects.get(type='platform').balance, Decimal('20.00'))

    def test_employee_finance_settings_validate_rate_and_sync_wallet(self):
        serializer = EmployeeSerializer(
            self.employee,
            data={
                'platform_commission_rate': Decimal('25.00'),
                'commission_balance': Decimal('70.00'),
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.wallet.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.platform_commission_rate, Decimal('25.00'))
        self.assertEqual(self.employee.commission_balance, Decimal('70.00'))
        self.assertEqual(self.wallet.balance, Decimal('70.00'))

        invalid = EmployeeSerializer(
            self.employee,
            data={'platform_commission_rate': Decimal('101.00')},
            partial=True,
        )
        self.assertFalse(invalid.is_valid())
