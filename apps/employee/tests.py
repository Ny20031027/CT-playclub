from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.account.models import User
from apps.customer.models import Customer
from apps.wx.models import GameCategory
from .models import (
    AddonValueAddedService, Employee, EmployeeGameRank, EmployeeSkill,
    EmployeeSkillRelation, GameRank, GameplayLevelOption, GameplayService,
    ServiceValueAdded, ValueAddedService
)
from .serializers import EmployeeSkillSerializer
from .views import EmployeeSkillViewSet
from .skill_services import sync_employee_rank_skills


class SkillSystemTests(TestCase):
    def setUp(self):
        self.game = GameCategory.objects.create(name='测试游戏', status=True)
        self.bronze = GameRank.objects.create(game_category=self.game, name='青铜', sort=10)
        self.gold = GameRank.objects.create(game_category=self.game, name='黄金', sort=20)
        self.bronze_skill = EmployeeSkill.objects.create(
            name='青铜陪玩', game_category=self.game, required_rank=self.bronze,
            assignment_mode='rank_auto', pricing_unit='hour', unit_price=Decimal('30'),
        )
        self.gold_skill = EmployeeSkill.objects.create(
            name='黄金排位', game_category=self.game, required_rank=self.gold,
            assignment_mode='rank_auto', pricing_unit='round', unit_price=Decimal('12'),
        )
        self.manual_skill = EmployeeSkill.objects.create(
            name='定制复盘', game_category=self.game, required_rank=self.bronze,
            assignment_mode='manual', pricing_unit='hour', unit_price=Decimal('80'),
        )
        user = User.objects.create_user(username='skill_tester')
        self.user = user
        self.client = APIClient()
        self.client.force_authenticate(user=user)
        self.employee = Employee.objects.create(
            user=user, employee_no='EMP-SKILL-001', real_name='测试打手'
        )

    def test_game_category_detail_uses_standard_response(self):
        payload = self.client.get(
            f'/api/system/game-categories/{self.game.id}/'
        ).json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['id'], self.game.id)
        self.assertEqual(payload['data']['name'], self.game.name)

    def test_game_rank_can_be_created_for_selected_category(self):
        payload = self.client.post('/api/employee/game-ranks/', {
            'game_category': self.game.id,
            'name': '钻石',
            'sort': 30,
            'status': True,
        }, format='json').json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['game_category'], self.game.id)
        self.assertTrue(GameRank.objects.filter(
            game_category=self.game, name='钻石', is_deleted=False
        ).exists())

    def set_rank(self, rank):
        relation, _ = EmployeeGameRank.objects.get_or_create(
            employee=self.employee, game_category=self.game,
            defaults={'rank': rank},
        )
        relation.rank = rank
        relation.is_deleted = False
        relation.save()
        sync_employee_rank_skills(self.employee, self.game.id)

    def test_rank_upgrade_and_downgrade_recalculate_auto_skills(self):
        self.set_rank(self.bronze)
        active_ids = set(EmployeeSkillRelation.objects.filter(
            employee=self.employee, is_deleted=False
        ).values_list('skill_id', flat=True))
        self.assertEqual(active_ids, {self.bronze_skill.id})

        self.set_rank(self.gold)
        active_ids = set(EmployeeSkillRelation.objects.filter(
            employee=self.employee, is_deleted=False
        ).values_list('skill_id', flat=True))
        self.assertEqual(active_ids, {self.bronze_skill.id, self.gold_skill.id})

        self.set_rank(self.bronze)
        active_ids = set(EmployeeSkillRelation.objects.filter(
            employee=self.employee, is_deleted=False
        ).values_list('skill_id', flat=True))
        self.assertEqual(active_ids, {self.bronze_skill.id})

    def test_manual_skill_and_custom_price_are_not_removed_by_rank_sync(self):
        EmployeeSkillRelation.objects.create(
            employee=self.employee, skill=self.manual_skill,
            assignment_source='manual', price_overridden=True,
            unit_price=Decimal('99.00'), is_enabled=False,
        )
        self.set_rank(self.gold)
        manual = EmployeeSkillRelation.objects.get(
            employee=self.employee, skill=self.manual_skill
        )
        self.assertFalse(manual.is_deleted)
        self.assertFalse(manual.is_enabled)
        self.assertEqual(manual.unit_price, Decimal('99.00'))

    def test_manual_self_service_skill_only_requires_game_category(self):
        serializer = EmployeeSkillSerializer(data={
            'name': '自助下单技能',
            'game_category': self.game.id,
            'required_rank': None,
            'assignment_mode': 'manual',
            'self_service_enabled': True,
            'unit_price': '0.00',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        skill = serializer.save()
        self.assertEqual(skill.game_category, self.game)
        self.assertIsNone(skill.required_rank)

    def test_rank_auto_skill_still_requires_rank(self):
        serializer = EmployeeSkillSerializer(data={
            'name': '自动授予技能',
            'game_category': self.game.id,
            'required_rank': None,
            'assignment_mode': 'rank_auto',
            'unit_price': '0.00',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('required_rank', serializer.errors)

    def test_auto_skill_uses_template_price_and_preserves_dasher_switch(self):
        self.set_rank(self.bronze)
        relation = EmployeeSkillRelation.objects.get(
            employee=self.employee, skill=self.bronze_skill
        )
        relation.is_enabled = False
        relation.save(update_fields=['is_enabled'])
        self.bronze_skill.unit_price = Decimal('35.00')
        self.bronze_skill.save(update_fields=['unit_price'])
        sync_employee_rank_skills(self.employee, self.game.id)
        relation.refresh_from_db()
        self.assertFalse(relation.is_enabled)
        self.assertEqual(relation.unit_price, Decimal('35.00'))

    def test_addon_value_added_services_are_saved_and_serialized(self):
        EmployeeSkillViewSet()._sync_gameplays(self.manual_skill, [{
            'name': '排位陪练',
            'settlement_unit': 'hour',
            'min_quantity': 1,
            'quantity_step': 1,
            'base_price': 50,
            'levels': [{'name': '标准', 'price_delta': 0}],
            'services': [{
                'name': '单排',
                'price_delta': 0,
                'value_added_services': [{
                    'name': '战术复盘',
                    'description': '本局结束后复盘',
                    'price': 7,
                    'status': True,
                }],
            }],
            'value_added_services': [{
                'name': '指定英雄',
                'price': 5,
                'value_added_services': [{
                    'name': '高难英雄',
                    'description': '限定高操作英雄',
                    'price': 12,
                    'sort': 1,
                    'status': True,
                }],
            }],
        }])

        addon = ValueAddedService.objects.get(name='指定英雄')
        addon_value = AddonValueAddedService.objects.get(addon=addon)
        self.assertEqual(addon_value.name, '高难英雄')
        self.assertEqual(addon_value.price, Decimal('12.00'))

        payload = EmployeeSkillSerializer(self.manual_skill).data
        saved_addon = payload['gameplays'][0]['value_added_services'][0]
        self.assertEqual(saved_addon['value_added_services'][0]['name'], '高难英雄')

        self.manual_skill.self_service_enabled = True
        self.manual_skill.save(update_fields=['self_service_enabled'])
        catalog = self.client.get('/api/wx/skills/self-service/').json()['data']
        gameplay_payload = catalog[0]['gameplays'][0]
        self.assertEqual(
            gameplay_payload['value_added_services'][0]['value_added_services'][0]['name'],
            '高难英雄',
        )
        self.assertEqual(
            gameplay_payload['services'][0]['value_added_services'][0]['name'],
            '战术复盘',
        )

        customer = Customer.objects.create(
            user=self.user, nickname='自助下单客户', coins=1000
        )
        gameplay = self.manual_skill.self_service_gameplays.get(name='排位陪练')
        level = GameplayLevelOption.objects.get(gameplay=gameplay, name='标准')
        service = GameplayService.objects.get(gameplay=gameplay, name='单排')
        service_value = ServiceValueAdded.objects.get(service=service, name='战术复盘')
        order_payload = self.client.post('/api/wx/orders/create-self-service/', {
            'gameplay_id': gameplay.id,
            'level_id': level.id,
            'service_id': service.id,
            'companion_type': 'single',
            'gender_requirement': 'any',
            'quantity': 1,
            'addon_ids': [addon.id],
            'addon_value_ids': [addon_value.id],
            'service_value_ids': [service_value.id],
        }, format='json').json()
        self.assertEqual(order_payload['code'], 200)
        snapshot = order_payload['data']['snapshot']
        self.assertEqual(snapshot['addon_value_ids'], [addon_value.id])
        self.assertEqual(snapshot['service_value_ids'], [service_value.id])
        self.assertEqual(snapshot['extra_price_delta'], 24.0)
        self.assertEqual(order_payload['data']['total_amount'], 74.0)
        customer.refresh_from_db()
        self.assertEqual(customer.coins, 260)
