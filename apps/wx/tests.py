from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill
from apps.notice.models import UserNotice
from apps.order.models import Order, OrderMember


class MultiPersonOrderFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.skill = EmployeeSkill.objects.create(name='Flow Skill', category='test', status=True)

        self.customer_user = User.objects.create_user(username='flow_customer')
        self.customer = Customer.objects.create(user=self.customer_user, nickname='Flow Customer')

        self.leader = self.create_employee('leader', 'EMP-FLOW-001')
        self.member = self.create_employee('member', 'EMP-FLOW-002')
        self.outsider = self.create_employee('outsider', 'EMP-FLOW-003')

    def create_employee(self, username, employee_no):
        user = User.objects.create_user(username=username)
        return Employee.objects.create(
            user=user,
            employee_no=employee_no,
            real_name=username,
            nickname=username,
            status='idle',
            online_status=True,
        )

    def create_multi_order(self):
        return Order.objects.create(
            order_no='FLOW202607170001',
            customer=self.customer,
            skill=self.skill,
            title='Multi order flow',
            order_type='self_service',
            quantity=2,
            duration=60,
            unit_price=Decimal('50.00'),
            total_amount=Decimal('100.00'),
            pay_amount=Decimal('100.00'),
            status='published',
            platform='mini_program',
        )

    def post_as(self, user, url, data=None):
        self.client.force_authenticate(user=user)
        return self.client.post(url, data or {}, format='json').json()

    def get_as(self, user, url):
        self.client.force_authenticate(user=user)
        return self.client.get(url).json()

    def test_multi_order_requires_all_members_before_start(self):
        order = self.create_multi_order()

        first = self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        self.assertEqual(first['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'published')
        self.assertEqual(order.locked_slots, 1)
        self.assertEqual(order.leader_id, self.leader.id)

        start_before_full = self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/start/')
        self.assertNotEqual(start_before_full['code'], 200)

        multi_slot = self.post_as(self.member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 2})
        self.assertNotEqual(multi_slot['code'], 200)

        second = self.post_as(self.member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        self.assertEqual(second['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirming')
        self.assertEqual(order.locked_slots, 2)

        detail = self.get_as(self.leader.user, f'/api/wx/orders/{order.id}/')
        self.assertFalse(detail['data']['can_invite'])
        self.assertTrue(detail['data']['is_formally_claimed'])

    def test_only_leader_can_operate_after_formal_claim(self):
        order = self.create_multi_order()
        self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        self.post_as(self.member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})

        non_leader_give_up = self.post_as(self.member.user, f'/api/wx/orders/{order.id}/give-up/')
        self.assertNotEqual(non_leader_give_up['code'], 200)

        confirmed = self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/confirm/')
        self.assertEqual(confirmed['code'], 200)

        non_leader_start = self.post_as(self.member.user, f'/api/wx/orders/{order.id}/start/')
        self.assertNotEqual(non_leader_start['code'], 200)

        started = self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/start/')
        self.assertEqual(started['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_progress')
        self.assertEqual(set(order.order_members.values_list('status', flat=True)), {'in_progress'})

        ended = self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/end/')
        self.assertEqual(ended['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    def test_order_invite_sends_notice_without_locking_slot(self):
        order = self.create_multi_order()
        self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})

        invite = self.post_as(
            self.leader.user,
            f'/api/wx/orders/{order.id}/invite/',
            {'target_id': self.member.id},
        )
        self.assertEqual(invite['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.locked_slots, 1)
        self.assertEqual(OrderMember.objects.filter(order=order).count(), 1)
        self.assertEqual(UserNotice.objects.filter(user=self.member.user).count(), 1)

        outsider_invite = self.post_as(
            self.outsider.user,
            f'/api/wx/orders/{order.id}/invite/',
            {'target_id': self.member.id},
        )
        self.assertNotEqual(outsider_invite['code'], 200)

    def test_leader_transfer_reopens_order_and_clears_team(self):
        order = self.create_multi_order()
        self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        self.post_as(self.member.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/confirm/')
        self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/start/')

        transfer = self.post_as(
            self.leader.user,
            f'/api/wx/orders/{order.id}/transfer/',
            {'reason': 'flow test transfer'},
        )
        self.assertEqual(transfer['code'], 200)
        order.refresh_from_db()
        self.leader.refresh_from_db()
        self.member.refresh_from_db()

        self.assertEqual(order.status, 'published')
        self.assertEqual(order.locked_slots, 0)
        self.assertIsNone(order.leader_id)
        self.assertEqual(OrderMember.objects.filter(order=order).count(), 0)
        self.assertEqual(self.leader.status, 'idle')
        self.assertEqual(self.member.status, 'idle')

    def test_single_order_stale_member_state_is_synced(self):
        order = self.create_multi_order()
        order.quantity = 1
        order.locked_slots = 0
        order.status = 'published'
        order.save(update_fields=['quantity', 'locked_slots', 'status'])

        OrderMember.objects.create(
            order=order,
            employee=self.leader,
            skill=self.skill,
            unit_price=Decimal('50.00'),
            duration=60,
            amount=Decimal('50.00'),
            status='accepted',
            remark='锁定1个席位',
        )

        detail = self.get_as(self.leader.user, f'/api/wx/orders/{order.id}/')
        self.assertEqual(detail['data']['remaining_slots'], 0)
        self.assertFalse(detail['data']['can_invite'])
        self.assertTrue(detail['data']['can_give_up'])

        order.refresh_from_db()
        self.assertEqual(order.status, 'confirming')
        self.assertEqual(order.locked_slots, 1)
        self.assertEqual(order.leader_id, self.leader.id)
