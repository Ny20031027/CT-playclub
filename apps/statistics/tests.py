import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill
from apps.order.models import Order, OrderMember


class DasherOrderRankTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(username='stats-admin')
        self.client.force_authenticate(user=self.admin)
        self.skill = EmployeeSkill.objects.create(
            name='统计技能', category='test', status=True
        )
        self.first_employee = self.create_employee('first')
        self.second_employee = self.create_employee('second')
        self.first_customer = self.create_customer('first', '111111111')
        self.second_customer = self.create_customer('second', '222222222')

    def create_employee(self, suffix):
        user = User.objects.create_user(username=f'dasher-{suffix}')
        return Employee.objects.create(
            user=user,
            employee_no=f'RANK-{suffix}',
            real_name=f'打手{suffix}',
            nickname=f'打手{suffix}',
            status='idle',
        )

    def create_customer(self, suffix, display_id):
        user = User.objects.create_user(
            username=f'customer-{suffix}',
            display_id=display_id,
        )
        return Customer.objects.create(
            user=user,
            nickname=f'老板{suffix}',
        )

    def create_order(
        self, order_no, customer, employee, created_at=None, amount=100,
        assigned=False, create_member=True
    ):
        order = Order.objects.create(
            order_no=order_no,
            customer=customer,
            assigned_employee=employee if assigned else None,
            skill=self.skill,
            status='published',
            order_type='self_service',
            quantity=1,
            duration=60,
            unit_price=Decimal(str(amount)),
            total_amount=Decimal(str(amount)),
            pay_amount=Decimal(str(amount)),
        )
        if create_member:
            OrderMember.objects.create(
                order=order,
                employee=employee,
                skill=self.skill,
                unit_price=Decimal(str(amount)),
                duration=60,
                amount=Decimal(str(amount)),
                status='assigned',
            )
        if created_at:
            Order.objects.filter(id=order.id).update(created_at=created_at)
            OrderMember.objects.filter(order=order).update(created_at=created_at)
            order.refresh_from_db()
        return order

    def test_monthly_dasher_order_rank_and_detail(self):
        now = timezone.now()
        last_month = now - datetime.timedelta(days=40)
        self.create_order('MONTH-RANK-001', self.first_customer, self.first_employee, assigned=True, amount=120)
        second = self.create_order(
            'MONTH-RANK-002', self.second_customer, self.first_employee,
            assigned=True, create_member=False, amount=80
        )
        self.create_order('MONTH-RANK-003', self.first_customer, self.second_employee, amount=60)
        self.create_order('MONTH-RANK-OLD', self.first_customer, self.first_employee, created_at=last_month, amount=200)

        rank_payload = self.client.get(
            '/api/statistics/stats/dasher-order-rank/?period=month&limit=5'
        ).json()

        self.assertEqual(rank_payload['code'], 200)
        self.assertEqual(rank_payload['data']['period'], 'month')
        rank_list = rank_payload['data']['results']
        self.assertEqual(rank_list[0]['employee_id'], self.first_employee.id)
        self.assertEqual(rank_list[0]['order_count'], 2)
        self.assertEqual(rank_list[1]['employee_id'], self.second_employee.id)
        self.assertEqual(rank_list[1]['order_count'], 1)

        detail_payload = self.client.get(
            f'/api/statistics/stats/dasher-order-detail/?period=month&employee_id={self.first_employee.id}'
        ).json()

        self.assertEqual(detail_payload['code'], 200)
        detail = detail_payload['data']
        self.assertEqual(detail['order_count'], 2)
        self.assertEqual(
            {order['order_no'] for order in detail['orders']},
            {'MONTH-RANK-001', second.order_no},
        )

    def test_wx_dasher_dashboard_returns_monthly_customer_top_five(self):
        self.client.force_authenticate(user=self.first_employee.user)
        self.create_order('CUSTOMER-RANK-001', self.first_customer, self.first_employee, assigned=True, amount=100)
        self.create_order(
            'CUSTOMER-RANK-002', self.first_customer, self.first_employee,
            assigned=True, create_member=False, amount=100
        )
        self.create_order('CUSTOMER-RANK-003', self.second_customer, self.first_employee, amount=100)
        self.create_order('CUSTOMER-RANK-OTHER', self.first_customer, self.second_employee, amount=100)

        payload = self.client.get('/api/wx/dasher/dashboard/').json()

        self.assertEqual(payload['code'], 200)
        customer_ranking = payload['data']['customer_ranking']
        self.assertEqual(customer_ranking[0]['customer_id'], self.first_customer.id)
        self.assertEqual(customer_ranking[0]['order_count'], 2)
        self.assertEqual(customer_ranking[0]['display_id'], '111111111')
        self.assertEqual(customer_ranking[1]['customer_id'], self.second_customer.id)
        self.assertEqual(customer_ranking[1]['order_count'], 1)
