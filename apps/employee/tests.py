from decimal import Decimal

from django.test import TestCase

from apps.account.models import User
from apps.wx.models import GameCategory
from .models import (
    Employee, EmployeeGameRank, EmployeeSkill, EmployeeSkillRelation, GameRank
)
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
        self.employee = Employee.objects.create(
            user=user, employee_no='EMP-SKILL-001', real_name='测试打手'
        )

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
