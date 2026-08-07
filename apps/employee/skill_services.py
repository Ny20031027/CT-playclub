from django.db import transaction

from .models import EmployeeGameRank, EmployeeSkill, EmployeeSkillRelation


@transaction.atomic
def sync_employee_rank_skills(employee, game_category_id=None):
    """Synchronize rank-auto skills without touching administrator assignments."""
    rank_rows = EmployeeGameRank.objects.filter(
        employee=employee, is_deleted=False, rank__status=True, rank__is_deleted=False
    ).select_related('rank')
    if game_category_id is not None:
        rank_rows = rank_rows.filter(game_category_id=game_category_id)

    rank_sort_by_category = {
        row.game_category_id: row.rank.sort
        for row in rank_rows
    }
    category_ids = set(rank_sort_by_category)
    if game_category_id is not None:
        category_ids.add(int(game_category_id))

    skills = EmployeeSkill.objects.filter(
        assignment_mode='rank_auto', status=True, is_deleted=False,
        game_category_id__in=category_ids,
        required_rank__status=True, required_rank__is_deleted=False,
    ).select_related('required_rank')
    eligible = {
        skill.id: skill
        for skill in skills
        if skill.required_rank.sort <= rank_sort_by_category.get(skill.game_category_id, -1)
    }

    existing = EmployeeSkillRelation.objects.filter(
        employee=employee,
        skill__game_category_id__in=category_ids,
    ).select_related('skill')
    existing_by_skill = {row.skill_id: row for row in existing}

    for skill_id, relation in existing_by_skill.items():
        should_remove = (
            relation.assignment_source == 'rank_auto' or
            relation.skill.assignment_mode == 'rank_auto'
        ) and skill_id not in eligible
        if should_remove and not relation.is_deleted:
            relation.is_deleted = True
            relation.save(update_fields=['is_deleted', 'updated_at'])

    for skill_id, skill in eligible.items():
        relation = existing_by_skill.get(skill_id)
        if relation is None:
            EmployeeSkillRelation.objects.create(
                employee=employee,
                skill=skill,
                unit_price=skill.unit_price,
                assignment_source='rank_auto',
                price_overridden=False,
                is_enabled=True,
            )
            continue
        update_fields = []
        if relation.assignment_source != 'rank_auto':
            relation.assignment_source = 'rank_auto'
            relation.price_overridden = False
            update_fields.extend(['assignment_source', 'price_overridden'])
        if relation.is_deleted:
            relation.is_deleted = False
            relation.is_enabled = True
            update_fields.extend(['is_deleted', 'is_enabled'])
        if not relation.price_overridden and relation.unit_price != skill.unit_price:
            relation.unit_price = skill.unit_price
            update_fields.append('unit_price')
        if update_fields:
            update_fields.append('updated_at')
            relation.save(update_fields=update_fields)


def sync_rank_auto_skill(skill):
    """Re-evaluate one auto skill for every employee ranked in its game."""
    if not skill.game_category_id:
        return
    employee_ids = EmployeeGameRank.objects.filter(
        game_category_id=skill.game_category_id, is_deleted=False
    ).values_list('employee_id', flat=True).distinct()
    from .models import Employee
    for employee in Employee.objects.filter(id__in=employee_ids, is_deleted=False):
        sync_employee_rank_skills(employee, skill.game_category_id)
