from decimal import Decimal

from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill
from apps.notice.models import Notice
from apps.order.models import Order


class Command(BaseCommand):
    help = 'Run a real database/API simulation for the multi-person order seat flow.'

    prefix = 'SIM_MULTI_FLOW_'

    def add_arguments(self, parser):
        parser.add_argument('--keep-data', action='store_true', help='Keep generated simulation data.')

    def handle(self, *args, **options):
        keep_data = options['keep_data']
        self.cleanup()

        customer_user = User.objects.create_user(username=f'{self.prefix}customer')
        customer = Customer.objects.create(user=customer_user, nickname='模拟客户')
        leader = self.create_employee('leader', '001')
        member = self.create_employee('member', '002')
        outsider = self.create_employee('outsider', '003')
        skill = EmployeeSkill.objects.create(name=f'{self.prefix}skill', category='simulation', status=True)
        order = Order.objects.create(
            order_no=f'{self.prefix}ORDER001',
            customer=customer,
            skill=skill,
            title='多人订单席位真实流程模拟',
            order_type='self_service',
            quantity=2,
            duration=60,
            unit_price=Decimal('50.00'),
            total_amount=Decimal('100.00'),
            pay_amount=Decimal('100.00'),
            status='published',
            platform='mini_program',
        )

        client = APIClient()

        try:
            self.assert_api(client, leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1}, 200, '队长接取第1席')
            self.assert_api(client, leader.user, f'/api/wx/orders/{order.id}/start/', {}, 400, '未满员禁止开始')
            self.assert_api(client, leader.user, f'/api/wx/orders/{order.id}/invite/', {'target_id': member.id}, 200, '队长邀请成员')
            self.assert_api(client, outsider.user, f'/api/wx/orders/{order.id}/invite/', {'target_id': member.id}, 400, '非队长禁止邀请')
            self.assert_api(client, member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 2}, 400, '禁止单人多席')
            self.assert_api(client, member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1}, 200, '成员接取第2席')

            order.refresh_from_db()
            if order.status != 'confirming' or order.locked_slots != 2 or order.leader_id != leader.id:
                raise AssertionError('席位满员后订单未进入正式接取状态')

            self.assert_api(client, member.user, f'/api/wx/orders/{order.id}/give-up/', {}, 400, '正式接取后非队长禁止放弃')
            self.assert_api(client, customer_user, f'/api/wx/orders/{order.id}/confirm/', {}, 200, '客户确认订单')
            self.assert_api(client, member.user, f'/api/wx/orders/{order.id}/start/', {}, 400, '非队长禁止开始')
            self.assert_api(client, leader.user, f'/api/wx/orders/{order.id}/start/', {}, 200, '队长开始服务')
            self.assert_api(client, customer_user, f'/api/wx/orders/{order.id}/end/', {}, 200, '客户结束订单')

            order.refresh_from_db()
            if order.status != 'completed':
                raise AssertionError('订单未完成全流程')

            self.stdout.write(self.style.SUCCESS('多人订单真实接口流程模拟通过'))
        finally:
            if keep_data:
                self.stdout.write(self.style.WARNING(f'保留模拟数据，订单号：{order.order_no}'))
            else:
                self.cleanup()

    def create_employee(self, role, suffix):
        user = User.objects.create_user(username=f'{self.prefix}{role}')
        return Employee.objects.create(
            user=user,
            employee_no=f'SIM-FLOW-{suffix}',
            real_name=f'模拟{role}',
            nickname=f'模拟{role}',
            status='idle',
            online_status=True,
        )

    def assert_api(self, client, user, url, data, expected_code, label):
        client.force_authenticate(user=user)
        response = client.post(url, data, format='json')
        payload = response.json()
        code = payload.get('code')
        if code != expected_code:
            raise AssertionError(f'{label}失败：期望 code={expected_code}，实际 code={code}，响应={payload}')
        self.stdout.write(f'OK - {label}')

    def cleanup(self):
        Order.objects.filter(order_no__startswith=self.prefix).delete()
        Notice.objects.filter(title__startswith='订单接取邀请', content__contains=self.prefix).delete()
        Employee.objects.filter(user__username__startswith=self.prefix).delete()
        Customer.objects.filter(user__username__startswith=self.prefix).delete()
        User.objects.filter(username__startswith=self.prefix).delete()
        EmployeeSkill.objects.filter(name__startswith=self.prefix).delete()
