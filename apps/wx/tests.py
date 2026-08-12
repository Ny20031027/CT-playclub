from decimal import Decimal
from unittest.mock import patch
import requests

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer, CustomerService
from apps.employee.models import (
    Employee, EmployeeGameRank, EmployeeSkill, EmployeeSkillRelation, GameRank,
    GameplayLevelOption, GameplayPresetItem, GameplayService, SkillGameplay,
)
from apps.notice.models import UserNotice
from apps.order.models import Order, OrderCandidate, OrderComment, OrderMember
from apps.system.models import Config, Coupon, UserCoupon
from apps.wx.models import Announcement, GameAccount, GameCategory, PreOrder, WxUser


class CustomerServicePreOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game = GameCategory.objects.create(name='预下单测试游戏', status=True)
        self.skill = EmployeeSkill.objects.create(
            name='预下单测试服务', game_category=self.game,
            self_service_enabled=True, status=True,
        )
        self.gameplay = SkillGameplay.objects.create(
            skill=self.skill, name='护航', order_mode='preset', status=True,
        )
        self.preset = GameplayPresetItem.objects.create(
            gameplay=self.gameplay, name='测试订单', display_image='/media/test.png',
            content='完整订单内容', price=Decimal('0.00'), status=True,
        )
        self.cs_user = User.objects.create_user(username='preorder_cs')
        cs_customer = Customer.objects.create(user=self.cs_user, nickname='预下单客服')
        CustomerService.objects.create(customer=cs_customer, status='online')
        self.customer_user = User.objects.create_user(username='preorder_customer')
        Customer.objects.create(user=self.customer_user, nickname='扫码客户', coins=0)
        self.selections = {
            'skill_id': self.skill.id,
            'skill_name': self.skill.name,
            'gameplay_id': self.gameplay.id,
            'gameplay_name': self.gameplay.name,
            'gameplay_order_mode': 'preset',
            'preset_item_id': self.preset.id,
            'preset_item_name': self.preset.name,
            'quantity': 1,
            'trial_requested': False,
            'employee_id': 0,
        }

    def _create_preorder(self):
        self.client.force_authenticate(user=self.cs_user)
        return self.client.post(
            '/api/wx/preorder/create/', {'selections': self.selections}, format='json'
        ).json()

    def test_only_customer_service_can_create_preorder(self):
        self.client.force_authenticate(user=self.customer_user)
        denied = self.client.post(
            '/api/wx/preorder/create/', {'selections': self.selections}, format='json'
        ).json()
        self.assertNotEqual(denied['code'], 200)

        created = self._create_preorder()
        self.assertEqual(created['code'], 200)
        self.assertIn('/qrcode/', created['data']['qr_url'])

    def test_preorder_is_consumed_once_by_customer_checkout(self):
        created = self._create_preorder()
        preorder_id = created['data']['id']
        payload = {
            'preorder_id': preorder_id,
            'gameplay_id': self.gameplay.id,
            'preset_item_id': self.preset.id,
            'quantity': 1,
            'trial_requested': False,
        }
        self.client.force_authenticate(user=self.customer_user)
        first = self.client.post(
            '/api/wx/orders/create-self-service/', payload, format='json'
        ).json()
        self.assertEqual(first['code'], 200)
        self.assertEqual(PreOrder.objects.get(id=preorder_id).status, 'used')

        second = self.client.post(
            '/api/wx/orders/create-self-service/', payload, format='json'
        ).json()
        self.assertNotEqual(second['code'], 200)
        self.assertIn('不能重复下单', second['msg'])

    @patch('apps.wx.views._get_wx_access_token', return_value='test-token')
    @patch('apps.wx.views.requests.Session')
    def test_qrcode_uses_official_mini_program_code(self, mocked_session, _mocked_token):
        created = self._create_preorder()
        session = mocked_session.return_value
        response_mock = session.post.return_value
        response_mock.headers = {'Content-Type': 'image/png'}
        response_mock.content = b'png-content'
        response_mock.raise_for_status.return_value = None

        self.client.force_authenticate(user=None)
        response = self.client.get(created['data']['qr_url'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'png-content')
        self.assertFalse(session.trust_env)
        call_payload = session.post.call_args.kwargs['json']
        self.assertEqual(call_payload['scene'], f"po={created['data']['id']}")
        self.assertEqual(call_payload['page'], 'pages/preorder-checkout/preorder-checkout')

    @patch('apps.wx.views.requests.Session')
    def test_access_token_request_bypasses_proxy_environment(self, mocked_session):
        from django.core.cache import cache
        from apps.wx.views import _get_wx_access_token

        cache.delete('wx_mini_program_access_token')
        session = mocked_session.return_value
        response = session.get.return_value
        response.json.return_value = {'access_token': 'fresh-token', 'expires_in': 7200}
        response.raise_for_status.return_value = None

        self.assertEqual(_get_wx_access_token(), 'fresh-token')
        self.assertFalse(session.trust_env)
        self.assertEqual(session.get.call_args.args[0], 'https://api.weixin.qq.com/cgi-bin/token')

    @patch('apps.wx.views.requests.Session')
    def test_access_token_retries_only_ssl_failure_for_wechat_host(self, mocked_session):
        from django.core.cache import cache
        from apps.wx.views import _get_wx_access_token

        cache.delete('wx_mini_program_access_token')
        session = mocked_session.return_value
        successful_response = session.get.return_value
        successful_response.json.return_value = {
            'access_token': 'fallback-token', 'expires_in': 7200,
        }
        successful_response.raise_for_status.return_value = None
        session.get.side_effect = [
            requests.exceptions.SSLError('self-signed certificate'),
            successful_response,
        ]

        self.assertEqual(_get_wx_access_token(), 'fallback-token')
        self.assertEqual(session.get.call_count, 2)
        self.assertNotIn('verify', session.get.call_args_list[0].kwargs)
        self.assertFalse(session.get.call_args_list[1].kwargs['verify'])
        self.assertFalse(session.get.call_args_list[1].kwargs['allow_redirects'])


class SelfServiceCouponCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game = GameCategory.objects.create(name='优惠券测试游戏', status=True)
        self.skill = EmployeeSkill.objects.create(
            name='优惠券测试服务', game_category=self.game,
            self_service_enabled=True, status=True,
        )
        self.gameplay = SkillGameplay.objects.create(
            skill=self.skill, name='预制玩法', order_mode='preset', status=True,
        )
        self.preset = GameplayPresetItem.objects.create(
            gameplay=self.gameplay, name='1000黑钻套餐', display_image='/media/test.png',
            content='套餐内容', price=Decimal('100.00'), required_people=2, status=True,
        )
        self.user = User.objects.create_user(username='coupon_checkout_user')
        self.customer = Customer.objects.create(user=self.user, nickname='优惠券用户', coins=1000)
        self.client.force_authenticate(user=self.user)

    def test_discount_coupon_pay_amount_is_used_on_order_detail(self):
        coupon = Coupon.objects.create(name='七折券', discount_rate=Decimal('70.00'))
        user_coupon = UserCoupon.objects.create(customer=self.customer, coupon=coupon)

        created = self.client.post('/api/wx/orders/create-self-service/', {
            'gameplay_id': self.gameplay.id,
            'preset_item_id': self.preset.id,
            'quantity': 1,
            'coupon_id': user_coupon.id,
        }, format='json').json()

        self.assertEqual(created['code'], 200)
        self.assertEqual(created['data']['total_amount'], 100.0)
        self.assertEqual(created['data']['pay_amount'], 70.0)
        self.assertEqual(created['data']['total_coins'], 700)

        order = Order.objects.get(id=created['data']['order_id'])
        self.assertEqual(order.total_amount, Decimal('100.00'))
        self.assertEqual(order.discount_amount, Decimal('30.00'))
        self.assertEqual(order.pay_amount, Decimal('70.00'))
        user_coupon.refresh_from_db()
        self.assertEqual(user_coupon.status, 'used')
        self.assertEqual(user_coupon.used_order_no, order.order_no)

        detail = self.client.get(f'/api/wx/orders/{order.id}/').json()
        self.assertEqual(detail['code'], 200)
        self.assertEqual(detail['data']['total_amount'], 100.0)
        self.assertEqual(detail['data']['discount_amount'], 30.0)
        self.assertEqual(detail['data']['pay_amount'], 70.0)
        self.assertEqual(detail['data']['self_service_snapshot']['total_coins'], 700)

    def test_selected_dasher_member_amount_uses_pre_coupon_total(self):
        coupon = Coupon.objects.create(name='七折券', discount_rate=Decimal('70.00'))
        user_coupon = UserCoupon.objects.create(customer=self.customer, coupon=coupon)
        dasher_user = User.objects.create_user(username='coupon_selected_dasher')
        dasher = Employee.objects.create(
            user=dasher_user, employee_no='COUPON-DASHER-001',
            real_name='优惠券打手', nickname='优惠券打手',
            status='idle', online_status=True,
        )

        created = self.client.post('/api/wx/orders/create-self-service/', {
            'gameplay_id': self.gameplay.id,
            'preset_item_id': self.preset.id,
            'quantity': 1,
            'coupon_id': user_coupon.id,
        }, format='json').json()
        order = Order.objects.get(id=created['data']['order_id'])
        OrderCandidate.objects.create(order=order, employee=dasher)

        selected = self.client.post('/api/wx/orders/{}/select-candidate/'.format(order.id), {
            'candidate_id': OrderCandidate.objects.get(order=order, employee=dasher).id,
        }, format='json').json()

        self.assertEqual(selected['code'], 200)
        member = OrderMember.objects.get(order=order, employee=dasher)
        self.assertEqual(member.amount, Decimal('50.00'))


class SelfServiceDispatchHallTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game = GameCategory.objects.create(name='自选单大厅测试游戏', status=True)
        self.skill = EmployeeSkill.objects.create(
            name='自选单大厅测试服务', game_category=self.game,
            self_service_enabled=True, status=True,
        )
        self.gameplay = SkillGameplay.objects.create(
            skill=self.skill, name='自选玩法', order_mode='custom',
            companion_mode='single', settlement_unit='hour',
            min_quantity=Decimal('1.00'), quantity_step=Decimal('1.00'),
            base_price=Decimal('0.00'), status=True,
        )
        self.level = GameplayLevelOption.objects.create(
            gameplay=self.gameplay, name='黄金', status=True,
        )
        self.service = GameplayService.objects.create(
            gameplay=self.gameplay, name='上分', status=True,
        )
        self.customer_user = User.objects.create_user(username='dispatch_customer')
        Customer.objects.create(user=self.customer_user, nickname='大厅客户', coins=0)
        self.dasher_user = User.objects.create_user(username='dispatch_dasher')
        self.dasher = Employee.objects.create(
            user=self.dasher_user, employee_no='DISPATCH-DASHER-001',
            real_name='大厅打手', nickname='大厅打手',
            status='idle', online_status=True,
        )

    def test_custom_self_service_order_without_reserved_dasher_is_listed(self):
        self.client.force_authenticate(user=self.customer_user)
        created = self.client.post('/api/wx/orders/create-self-service/', {
            'gameplay_id': self.gameplay.id,
            'level_id': self.level.id,
            'service_id': self.service.id,
            'companion_type': 'single',
            'quantity': 1,
        }, format='json').json()

        self.assertEqual(created['code'], 200)
        order = Order.objects.get(id=created['data']['order_id'])
        self.assertEqual(order.status, 'published')
        self.assertEqual(order.order_type, 'self_service')
        self.assertIsNone(order.assigned_employee_id)

        self.client.force_authenticate(user=self.dasher_user)
        hall = self.client.get('/api/wx/orders/dispatch-hall/').json()

        self.assertEqual(hall['code'], 200)
        listed = [item for item in hall['data']['list'] if item['id'] == order.id]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['order_type'], 'self_service')
        self.assertEqual(listed[0]['remaining_slots'], 1)
        self.assertTrue(listed[0]['can_claim'])

    def test_dispatch_hall_paginates_after_visibility_filtering(self):
        other_user = User.objects.create_user(username='dispatch_reserved_dasher')
        other_dasher = Employee.objects.create(
            user=other_user, employee_no='DISPATCH-DASHER-002',
            real_name='预约打手', nickname='预约打手',
            status='idle', online_status=True,
        )
        for index in range(10):
            Order.objects.create(
                order_no=f'DISPATCH-HIDDEN-{index}',
                customer=self.customer_user.customer,
                skill=self.skill,
                status='published',
                title=f'不可见指定单{index}',
                order_type='self_service',
                quantity=1,
                unit_price=Decimal('0.00'),
                total_amount=Decimal('0.00'),
                pay_amount=Decimal('0.00'),
                game_name=self.game.name,
                assigned_employee=other_dasher,
            )

        self.client.force_authenticate(user=self.customer_user)
        created = self.client.post('/api/wx/orders/create-self-service/', {
            'gameplay_id': self.gameplay.id,
            'level_id': self.level.id,
            'service_id': self.service.id,
            'companion_type': 'single',
            'quantity': 1,
        }, format='json').json()
        order = Order.objects.get(id=created['data']['order_id'])
        order.created_at = order.created_at.replace(year=2000)
        order.save(update_fields=['created_at'])

        self.client.force_authenticate(user=self.dasher_user)
        hall = self.client.get('/api/wx/orders/dispatch-hall/?page=1&page_size=10').json()

        self.assertEqual(hall['code'], 200)
        self.assertEqual(hall['data']['total'], 1)
        self.assertEqual([item['id'] for item in hall['data']['list']], [order.id])


class OfficialAnnouncementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='announcement_user')
        self.client.force_authenticate(user=self.user)

    def test_my_notices_returns_pinned_official_conversation(self):
        Announcement.objects.create(
            title='暑期活动',
            content='活动说明',
            image='/media/announcements/summer.png',
            status=True,
        )

        response = self.client.get('/api/wx/notices/').json()
        self.assertEqual(response['code'], 200)
        official = response['data']['official_conversation']
        self.assertEqual(official['title'], '官方公告')
        self.assertEqual(official['type'], 'official')
        self.assertTrue(official['is_pinned'])
        self.assertEqual(official['content'], '暑期活动')
        self.assertTrue(official['image'].endswith('/media/announcements/summer.png'))

    def test_official_announcements_only_returns_enabled_items(self):
        Announcement.objects.create(title='可见公告', content='公告内容', status=True)
        Announcement.objects.create(title='隐藏公告', content='隐藏内容', status=False)

        response = self.client.get('/api/wx/official-announcements/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['total'], 1)
        self.assertEqual(response['data']['list'][0]['title'], '可见公告')


class RechargeOfferTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='recharge_offer_user')
        self.client.force_authenticate(user=self.user)

    def test_recharge_offers_read_from_system_config(self):
        Config.objects.create(
            key='recharge_offers',
            value='[{"amount":50,"coins":500,"bonus_coins":50,"sort":0,"status":true}]',
            name='充值优惠',
            type='json',
            group='discount',
        )

        response = self.client.get('/api/wx/recharge-offers/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['list'][0]['amount'], 50.0)
        self.assertEqual(response['data']['list'][0]['coins'], 500)
        self.assertEqual(response['data']['list'][0]['bonus_coins'], 50)
        self.assertEqual(response['data']['list'][0]['total_coins'], 550)


class AgreementTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_agreement_detail_is_public_and_has_default_content(self):
        response = self.client.get('/api/wx/agreements/user_agreement/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['key'], 'user_agreement')
        self.assertEqual(response['data']['title'], '用户协议')
        self.assertIn('黑金电竞陪玩平台', response['data']['content'])

    def test_agreement_detail_reads_system_config(self):
        Config.objects.create(
            key='mini_agreements',
            value='[{"key":"privacy_policy","title":"新版隐私政策","summary":"新版摘要","content":"新版内容","sort":0,"status":true}]',
            name='小程序协议设置',
            type='json',
            group='agreement',
        )

        response = self.client.get('/api/wx/agreements/privacy_policy/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['title'], '新版隐私政策')
        self.assertEqual(response['data']['summary'], '新版摘要')
        self.assertEqual(response['data']['content'], '新版内容')

    def test_agreement_detail_converts_literal_newline_marks(self):
        Config.objects.create(
            key='mini_agreements',
            value='[{"key":"user_agreement","title":"用户协议","content":"第一行\\\\n第二行","sort":0,"status":true}]',
            name='小程序协议设置',
            type='json',
            group='agreement',
        )

        response = self.client.get('/api/wx/agreements/user_agreement/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['content'], '第一行\n第二行')


class EmployeeGameRankDisplayTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.game = GameCategory.objects.create(name='三角洲', status=True)
        self.rank = GameRank.objects.create(game_category=self.game, name='铂金', sort=1, status=True)
        self.user = User.objects.create_user(username='rank_dasher')
        self.employee = Employee.objects.create(
            user=self.user,
            employee_no='EMP-RANK-001',
            real_name='段位打手',
            nickname='段位打手',
            status='idle',
            is_star=True,
            star_sort=1,
        )
        self.employee.game_categories.add(self.game)
        EmployeeGameRank.objects.create(employee=self.employee, game_category=self.game, rank=self.rank)
        self.skill = EmployeeSkill.objects.create(
            name='三角洲护航',
            game_category=self.game,
            unit_price=Decimal('20.00'),
            status=True,
        )
        EmployeeSkillRelation.objects.create(
            employee=self.employee,
            skill=self.skill,
            unit_price=Decimal('20.00'),
            is_enabled=True,
        )

    def test_employee_list_returns_current_game_rank_badge(self):
        response = self.client.get(f'/api/wx/employees/?game_id={self.game.id}').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['list'][0]['game_rank_badge'], '三角洲-铂金')

    def test_employee_detail_skill_returns_game_rank_badge(self):
        response = self.client.get(f'/api/wx/employees/{self.employee.id}/').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['game_rank_badge'], '三角洲-铂金')
        self.assertEqual(response['data']['game_ranks'][0]['badge'], '三角洲-铂金')

    def test_star_filter_keeps_star_total_for_current_game(self):
        response = self.client.get(f'/api/wx/employees/?game_id={self.game.id}&sort=star').json()
        self.assertEqual(response['code'], 200)
        self.assertEqual(response['data']['star_total'], 1)
        self.assertEqual(response['data']['list'][0]['id'], self.employee.id)


class BlackGoldSearchTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_search_returns_dasher_but_hides_customer(self):
        dasher_user = User.objects.create_user(username='searchable_dasher')
        dasher_user.display_id = '123456789'
        dasher_user.save(update_fields=['display_id'])
        employee = Employee.objects.create(
            user=dasher_user,
            employee_no='EMP-SEARCH-001',
            real_name='可搜索打手',
            nickname='可搜索打手',
            status='idle',
        )
        customer_user = User.objects.create_user(username='hidden_customer')
        customer_user.display_id = '987654321'
        customer_user.save(update_fields=['display_id'])
        Customer.objects.create(user=customer_user, nickname='不可搜索客户')

        found = self.client.get('/api/wx/search/?id=123456789').json()
        hidden = self.client.get('/api/wx/search/?id=987654321').json()
        listed = self.client.get('/api/wx/employees/?page_size=10').json()

        self.assertEqual(found['code'], 200)
        self.assertEqual(found['data']['id'], employee.id)
        self.assertNotEqual(hidden['code'], 200)
        self.assertEqual(listed['data']['list'][0]['display_id'], '123456789')

    def test_profile_payload_contains_fixed_display_id(self):
        user = User.objects.create_user(username='profile_display_id')
        user.display_id = '112233445'
        user.save(update_fields=['display_id'])
        Customer.objects.create(user=user, nickname='资料用户')
        self.client.force_authenticate(user=user)

        first = self.client.get('/api/wx/profile/').json()
        second = self.client.get('/api/wx/profile/').json()

        self.assertEqual(first['data']['display_id'], '112233445')
        self.assertEqual(second['data']['display_id'], '112233445')

    @patch('apps.wx.role_views.get_wx_openid')
    def test_login_generates_display_id_once(self, get_wx_openid):
        get_wx_openid.return_value = {'openid': 'black_gold_login_openid', 'session_key': 'session'}

        first = self.client.post('/api/wx/login/', {'code': 'first'}, format='json').json()
        second = self.client.post('/api/wx/login/', {'code': 'second'}, format='json').json()

        self.assertEqual(first['code'], 200)
        self.assertRegex(first['data']['user_info']['display_id'], r'^\d{9}$')
        self.assertEqual(
            first['data']['user_info']['display_id'],
            second['data']['user_info']['display_id'],
        )
        self.assertEqual(WxUser.objects.filter(openid='black_gold_login_openid').count(), 1)


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

        leader_candidate = OrderCandidate.objects.get(order=order, employee=self.leader)
        member_candidate = OrderCandidate.objects.get(order=order, employee=self.member)
        self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/select-candidate/', {
            'candidate_id': leader_candidate.id,
        })
        self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/select-candidate/', {
            'candidate_id': member_candidate.id,
        })
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirming')

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

        customer_end = self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/end/')
        self.assertNotEqual(customer_end['code'], 200)

        member_detail = self.get_as(self.member.user, f'/api/wx/orders/{order.id}/')
        self.assertTrue(member_detail['data']['can_complete'])

        ended = self.post_as(self.member.user, f'/api/wx/orders/{order.id}/complete/')
        self.assertEqual(ended['code'], 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')

    def test_order_member_can_upload_completion_images_for_detail_viewers(self):
        order = self.create_multi_order()
        self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/claim/', {'slots': 1})
        leader_candidate = OrderCandidate.objects.get(order=order, employee=self.leader)
        self.post_as(self.customer_user, f'/api/wx/orders/{order.id}/select-candidate/', {
            'candidate_id': leader_candidate.id,
        })

        saved = self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/completion-images/', {
            'images': ['/media/complete/1.png', '/media/complete/2.png'],
        })
        self.assertEqual(saved['code'], 200)
        self.assertEqual(len(saved['data']['completion_images']), 2)

        customer_detail = self.get_as(self.customer_user, f'/api/wx/orders/{order.id}/')
        self.assertEqual(len(customer_detail['data']['completion_images']), 2)
        self.assertTrue(customer_detail['data']['completion_images'][0].endswith('/media/complete/1.png'))

        too_many = [f'/media/complete/{index}.png' for index in range(12)]
        trimmed = self.post_as(self.leader.user, f'/api/wx/orders/{order.id}/completion-images/', {
            'images': too_many,
        })
        self.assertEqual(trimmed['code'], 200)
        self.assertEqual(len(trimmed['data']['completion_images']), 9)

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
