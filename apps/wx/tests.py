from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill
from apps.notice.models import UserNotice
from apps.order.models import Order, OrderComment, OrderMember
from apps.wx.models import GameAccount, GameCategory


class GameAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game = GameCategory.objects.create(name='王者荣耀', status=True)
        self.customer_user = User.objects.create_user(username='game_customer')
        Customer.objects.create(user=self.customer_user, nickname='游戏客户')
        self.dasher_user = User.objects.create_user(username='game_dasher')
        Employee.objects.create(
            user=self.dasher_user,
            employee_no='EMP-GAME-001',
            real_name='游戏打手',
        )

    def save_as(self, user, account):
        self.client.force_authenticate(user=user)
        return self.client.post('/api/wx/game-accounts/save/', {
            'game_category_id': self.game.id,
            'game_account': account,
        }, format='json').json()

    def test_customer_and_dasher_can_save_game_accounts(self):
        customer_result = self.save_as(self.customer_user, 'customer-1001')
        dasher_result = self.save_as(self.dasher_user, 'dasher-2002')

        self.assertEqual(customer_result['code'], 200)
        self.assertEqual(dasher_result['code'], 200)
        self.assertTrue(GameAccount.objects.filter(
            user=self.customer_user, game_account='customer-1001', is_deleted=False
        ).exists())
        self.assertTrue(GameAccount.objects.filter(
            user=self.dasher_user, game_account='dasher-2002', is_deleted=False
        ).exists())

    def test_save_updates_existing_account_and_list_returns_database_value(self):
        self.save_as(self.customer_user, 'old-account')
        updated = self.save_as(self.customer_user, 'new-account')
        self.assertEqual(updated['code'], 200)
        self.assertEqual(GameAccount.objects.filter(
            user=self.customer_user, game_category=self.game
        ).count(), 1)

        listed = self.client.get('/api/wx/game-accounts/').json()
        self.assertEqual(listed['code'], 200)
        self.assertEqual(listed['data'][0]['game_account'], 'new-account')

    def test_deleted_account_is_hidden_and_can_be_added_again(self):
        saved = self.save_as(self.customer_user, 'first-account')
        account_id = saved['data']['id']
        deleted = self.client.post(
            '/api/wx/game-accounts/delete/', {'id': account_id}, format='json'
        ).json()
        self.assertEqual(deleted['code'], 200)
        self.assertEqual(self.client.get('/api/wx/game-accounts/').json()['data'], [])

        restored = self.save_as(self.customer_user, 'restored-account')
        self.assertEqual(restored['code'], 200)
        account = GameAccount.objects.get(id=account_id)
        self.assertFalse(account.is_deleted)
        self.assertEqual(account.game_account, 'restored-account')


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

    def test_single_order_comment_ignores_unassigned_placeholder_member(self):
        order = self.create_multi_order()
        order.quantity = 1
        order.status = 'completed'
        order.save(update_fields=['quantity', 'status'])

        placeholder = OrderMember.objects.create(
            order=order,
            skill=self.skill,
            unit_price=Decimal('50.00'),
            duration=60,
            amount=Decimal('50.00'),
            status='assigned',
        )
        actual_member = OrderMember.objects.create(
            order=order,
            employee=self.leader,
            skill=self.skill,
            unit_price=Decimal('50.00'),
            duration=60,
            amount=Decimal('50.00'),
            status='completed',
        )

        result = self.post_as(
            self.customer_user,
            f'/api/wx/orders/{order.id}/comment/',
            {'rating': 5, 'content': '服务很好', 'member_id': 0},
        )

        self.assertEqual(result['code'], 200)
        comment = OrderComment.objects.get(order=order)
        self.assertEqual(comment.member_id, actual_member.id)
        self.assertEqual(comment.employee_id, self.leader.id)
        self.assertNotEqual(comment.member_id, placeholder.id)
        order.refresh_from_db()
        self.assertEqual(order.status, 'reviewed')

    def test_multi_order_comment_requires_and_uses_member_id(self):
        order = self.create_multi_order()
        order.status = 'completed'
        order.save(update_fields=['status'])
        leader_member = OrderMember.objects.create(
            order=order, employee=self.leader, skill=self.skill,
            unit_price=Decimal('50.00'), duration=60,
            amount=Decimal('50.00'), status='completed',
        )
        member_member = OrderMember.objects.create(
            order=order, employee=self.member, skill=self.skill,
            unit_price=Decimal('50.00'), duration=60,
            amount=Decimal('50.00'), status='completed',
        )

        missing_member = self.post_as(
            self.customer_user, f'/api/wx/orders/{order.id}/comment/',
            {'rating': 5},
        )
        self.assertNotEqual(missing_member['code'], 200)

        first = self.post_as(
            self.customer_user, f'/api/wx/orders/{order.id}/comment/',
            {'rating': 5, 'member_id': leader_member.id},
        )
        self.assertEqual(first['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

        second = self.post_as(
            self.customer_user, f'/api/wx/orders/{order.id}/comment/',
            {'rating': 4, 'member_id': member_member.id},
        )
        self.assertEqual(second['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'reviewed')
        self.assertEqual(OrderComment.objects.filter(order=order).count(), 2)
