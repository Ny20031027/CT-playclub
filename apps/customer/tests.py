from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
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
