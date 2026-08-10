import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer, CustomerService, CustomerServiceConversation, CSMessage
from apps.employee.models import Employee
from apps.notice.models import UserNotice
from apps.order.models import Order, OrderMember, OrderChatGroup
from apps.schedule.models import CSSchedule
from apps.wx.views import _create_order_chat_group


class ServiceMessagingFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer_user = User.objects.create_user(username='group_customer', nickname='客户甲')
        self.customer = Customer.objects.create(user=self.customer_user, nickname='客户甲')
        self.cs_users = [self._create_scheduled_cs(index) for index in (1, 2)]

    def _create_scheduled_cs(self, index):
        user = User.objects.create_user(username=f'scheduled_cs_{index}', nickname=f'客服{index}')
        customer = Customer.objects.create(user=user, nickname=f'客服{index}')
        CustomerService.objects.create(customer=customer, status='online', work_status='on_duty')
        employee = Employee.objects.create(
            user=user, employee_no=f'CS{index:03d}', real_name=f'客服{index}',
            nickname=f'客服{index}', status='idle', online_status=True,
        )
        CSSchedule.objects.create(
            employee=employee,
            day_of_week=timezone.now().weekday(),
            start_time=datetime.time(0, 0),
            end_time=datetime.time(23, 59, 59),
            status=True,
        )
        return user

    def test_human_request_broadcasts_and_only_one_cs_can_claim(self):
        self.client.force_authenticate(self.customer_user)
        requested = self.client.post('/api/wx/cs/human/request/', {}, format='json').json()
        self.assertEqual(requested['code'], 200)
        conversation = CustomerServiceConversation.objects.get(id=requested['data']['conversation_id'])
        self.assertEqual(set(conversation.eligible_user_ids), {user.id for user in self.cs_users})
        self.assertEqual(UserNotice.objects.filter(user__in=self.cs_users).count(), 2)

        self.client.force_authenticate(self.cs_users[0])
        claimed = self.client.post(f'/api/wx/cs/human/{conversation.id}/claim/', {}, format='json').json()
        self.assertEqual(claimed['code'], 200)

        self.client.force_authenticate(self.cs_users[1])
        rejected = self.client.post(f'/api/wx/cs/human/{conversation.id}/claim/', {}, format='json').json()
        self.assertNotEqual(rejected['code'], 200)
        conversation.refresh_from_db()
        self.assertEqual(conversation.handler_id, self.cs_users[0].id)
        self.assertTrue(CSMessage.objects.filter(customer=self.customer, content__contains='客服1 已接入').exists())

        self.client.force_authenticate(self.customer_user)
        status = self.client.get('/api/wx/cs/human/status/').json()
        self.assertEqual(status['data']['status'], 'active')
        self.assertEqual(status['data']['handler_name'], '客服1')

    def test_order_group_contains_all_parties_and_expired_group_is_deleted(self):
        dasher_user = User.objects.create_user(username='group_dasher', nickname='打手甲')
        dasher = Employee.objects.create(
            user=dasher_user, employee_no='GROUP001', real_name='打手甲', nickname='打手甲',
            status='busy', online_status=True,
        )
        order = Order.objects.create(
            order_no='GROUP-ORDER-001', customer=self.customer, status='in_progress',
            quantity=1, locked_slots=1, unit_price=Decimal('10'), total_amount=Decimal('10'),
            pay_amount=Decimal('10'), platform='mini_program',
        )
        OrderMember.objects.create(order=order, employee=dasher, status='in_progress')

        group = _create_order_chat_group(order)
        self.assertEqual(set(group.members.values_list('role', flat=True)), {'customer', 'dasher', 'cs'})
        self.assertEqual(group.members.count(), 4)
        self.assertAlmostEqual((group.expires_at - timezone.now()).total_seconds(), 72 * 3600, delta=10)

        group.expires_at = timezone.now() - datetime.timedelta(seconds=1)
        group.save(update_fields=['expires_at'])
        self.client.force_authenticate(self.customer_user)
        response = self.client.get('/api/wx/chat-groups/').json()
        self.assertEqual(response['code'], 200)
        self.assertFalse(OrderChatGroup.objects.filter(id=group.id).exists())
