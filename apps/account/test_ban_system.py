from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customer.models import Customer
from apps.employee.models import Employee
from apps.wx.models import WxUser

from .ban_utils import apply_ban, ban_info, remove_ban
from .models import User
from .serializers import LoginSerializer


class BanSystemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='banned-user', password='test-pass', is_online=True
        )
        self.customer = Customer.objects.create(user=self.user, nickname='封禁测试客户')

    def test_apply_ban_supports_hours_days_and_forever(self):
        apply_ban(self.user, 'hours', 2, '小时封禁')
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_banned_active())
        self.assertFalse(self.user.is_online)
        self.assertIsNotNone(self.user.auth_invalid_before)
        self.assertIsNotNone(self.user.ban_until)
        self.assertEqual(ban_info(self.user)['ban_reason'], '小时封禁')

        remove_ban(self.user)
        apply_ban(self.user, 'days', 1, '按天封禁')
        self.user.refresh_from_db()
        self.assertGreater(self.user.ban_until, timezone.now() + timedelta(hours=23))

        remove_ban(self.user)
        apply_ban(self.user, 'forever', reason='永久封禁')
        self.user.refresh_from_db()
        self.assertTrue(ban_info(self.user)['permanent'])

    def test_apply_ban_rejects_invalid_duration(self):
        with self.assertRaises(ValueError):
            apply_ban(self.user, 'minutes', 10)
        with self.assertRaises(ValueError):
            apply_ban(self.user, 'hours', 0)

    def test_password_login_rejects_banned_user_with_deadline_and_reason(self):
        apply_ban(self.user, 'hours', 2, '违规操作')
        serializer = LoginSerializer(data={
            'username': self.user.username,
            'password': 'test-pass',
        })

        self.assertFalse(serializer.is_valid())
        message = str(serializer.errors)
        self.assertIn('账号已被封禁', message)
        self.assertIn('违规操作', message)
        self.assertIn('封禁至', message)

    def test_test_login_rejects_banned_customer(self):
        apply_ban(self.user, 'forever', reason='永久停用')

        response = APIClient().post(
            '/api/wx/test-login/', {'user_type': 'customer'}, format='json'
        ).json()

        self.assertEqual(response['code'], 4010)
        self.assertTrue(response['data']['permanent'])
        self.assertEqual(response['data']['ban_reason'], '永久停用')

    @patch('apps.wx.role_views.get_wx_openid')
    def test_real_wx_login_rejects_banned_customer_without_issuing_token(self, get_openid):
        get_openid.return_value = {
            'openid': 'banned-openid',
            'session_key': 'session-key',
        }
        WxUser.objects.create(openid='banned-openid', user=self.user)
        apply_ban(self.user, 'hours', 6, '多次违规')

        response = APIClient().post(
            '/api/wx/login/', {'code': 'wx-code'}, format='json'
        ).json()

        self.assertEqual(response['code'], 4010)
        self.assertEqual(response['msg'], '账号已被封禁，无法登录')
        self.assertEqual(response['data']['ban_reason'], '多次违规')
        self.assertTrue(response['data']['ban_until_display'])
        self.assertNotIn('token', response.get('data') or {})

    def test_ban_revokes_existing_token_even_after_unban(self):
        old_access = RefreshToken.for_user(self.user).access_token
        old_access['iat'] = int((timezone.now() - timedelta(minutes=1)).timestamp())
        access_token = str(old_access)
        apply_ban(self.user, 'hours', 1, '强制下线')
        remove_ban(self.user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/wx/profile/').json()

        self.assertEqual(response['code'], 401)
        self.assertTrue(response['data']['session_revoked'])

        new_access_token = RefreshToken.for_user(self.user).access_token
        self.user.refresh_from_db()
        self.assertGreaterEqual(
            int(new_access_token['iat']),
            int(self.user.auth_invalid_before.timestamp()),
            (new_access_token['iat'], self.user.auth_invalid_before),
        )
        new_client = APIClient()
        new_client.credentials(HTTP_AUTHORIZATION=f'Bearer {str(new_access_token)}')
        new_response = new_client.get('/api/wx/profile/').json()
        self.assertEqual(new_response['code'], 200, new_response)

    def test_active_ban_kicks_existing_session_offline(self):
        access_token = str(RefreshToken.for_user(self.user).access_token)
        apply_ban(self.user, 'days', 1, '恶意操作')

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = client.get('/api/wx/profile/').json()

        self.assertEqual(response['code'], 4010)
        self.assertEqual(response['data']['ban_reason'], '恶意操作')
        self.assertIn('ban_until_display', response['data'])

    def test_admin_can_ban_and_freeze_customer_and_employee(self):
        admin = User.objects.create_superuser(
            username='ban-admin', password='admin-pass'
        )
        employee_user = User.objects.create_user(username='freeze-employee')
        employee = Employee.objects.create(
            user=employee_user,
            employee_no='BAN-EMP-001',
            real_name='冻结测试打手',
            nickname='冻结测试打手',
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        customer_ban = client.post(
            f'/api/customer/customers/{self.customer.id}/ban/',
            {'duration_type': 'hours', 'duration': 3, 'reason': '客户违规'},
            format='json',
        ).json()
        customer_freeze = client.post(
            f'/api/customer/customers/{self.customer.id}/freeze-coins/',
            {'frozen': True}, format='json'
        ).json()
        employee_ban = client.post(
            f'/api/employee/employees/{employee.id}/ban/',
            {'duration_type': 'days', 'duration': 2, 'reason': '打手违规'},
            format='json',
        ).json()
        employee_freeze = client.post(
            f'/api/employee/employees/{employee.id}/freeze-commission/',
            {'frozen': True}, format='json'
        ).json()

        self.customer.refresh_from_db()
        employee.refresh_from_db()
        self.assertEqual(customer_ban['code'], 200)
        self.assertEqual(customer_freeze['code'], 200)
        self.assertTrue(self.customer.coins_frozen)
        self.assertEqual(employee_ban['code'], 200)
        self.assertEqual(employee_freeze['code'], 200)
        self.assertTrue(employee.commission_frozen)

        invalid = client.post(
            f'/api/employee/employees/{employee.id}/ban/',
            {'duration_type': 'hours', 'duration': 0}, format='json'
        ).json()
        self.assertEqual(invalid['code'], 400)
