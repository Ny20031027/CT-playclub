from django.db import migrations, models
from django.db.models import Count


def initialize_assessment_mode(apps, schema_editor):
    Employee = apps.get_model('employee', 'Employee')
    EmployeeSkillRelation = apps.get_model('employee', 'EmployeeSkillRelation')
    double_employee_ids = EmployeeSkillRelation.objects.filter(
        is_deleted=False
    ).values('employee_id').annotate(
        skill_count=Count('id')
    ).filter(skill_count__gt=1).values_list('employee_id', flat=True)
    Employee.objects.filter(id__in=double_employee_ids).update(
        assessment_mode='double'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('employee', '0027_addon_value_added_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='assessment_mode',
            field=models.CharField(
                choices=[('single', '单考'), ('double', '双考')],
                default='single', max_length=10, verbose_name='考核模式'
            ),
        ),
        migrations.RunPython(initialize_assessment_mode, migrations.RunPython.noop),
    ]
