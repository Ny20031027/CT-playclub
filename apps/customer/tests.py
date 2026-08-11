from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.system.models import Config
from .serializers import CustomerSerializer
from .models import Customer


class CustomerRechargeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='recharge_test')
        self.customer = Customer.objects.create(
            user=self.user,
            nickname='充值测试客户',
            balance=Decimal('5.00'),
            coins=750,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_recharge_returns_authoritative_balance(self):
        response = self.client.post(
            f'/api/customer/customers/{self.customer.id}/recharge/',
            {
                'amount': 10,
                'coins': 100,
                'ratio': 10,
                'payment_method': 'wechat',
            },
            format='json',
        )

        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['recharged_coins'], 100)
        self.assertEqual(payload['data']['coins'], 850)
        self.assertEqual(payload['data']['balance'], 15.0)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.coins, 850)
        self.assertEqual(self.customer.balance, Decimal('15.00'))

    def test_recharge_uses_configured_offer_and_ignores_client_coins(self):
        Config.objects.create(
            key='recharge_offers',
            value='[{"amount":50,"coins":500,"bonus_coins":50,"sort":0,"status":true}]',
            name='充值优惠',
            type='json',
            group='discount',
        )

        response = self.client.post(
            f'/api/customer/customers/{self.customer.id}/recharge/',
            {
                'amount': 50,
                'coins': 999999,
                'ratio': 10,
                'payment_method': 'wechat',
            },
            format='json',
        )

        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['recharged_coins'], 550)
        self.assertEqual(payload['data']['bonus_coins'], 50)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.coins, 1300)


class CustomerDisplayIdEditTests(TestCase):
    def test_customer_serializer_updates_unique_display_id(self):
        user = User.objects.create_user(username='customer_display_edit')
        user.display_id = '111111111'
        user.save(update_fields=['display_id'])
        customer = Customer.objects.create(user=user, nickname='客户ID编辑')

        serializer = CustomerSerializer(
            customer, data={'edit_display_id': '12345678'}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        user.refresh_from_db()
        self.assertEqual(user.display_id, '12345678')

    def test_customer_serializer_rejects_duplicate_display_id(self):
        owner = User.objects.create_user(username='customer_display_owner')
        owner.display_id = '222222222'
        owner.save(update_fields=['display_id'])
        target_user = User.objects.create_user(username='customer_display_target')
        customer = Customer.objects.create(user=target_user, nickname='目标客户')

        serializer = CustomerSerializer(
            customer, data={'edit_display_id': '222222222'}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('edit_display_id', serializer.errors)
