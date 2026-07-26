from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0014_add_skill_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeskill',
            name='min_people',
            field=models.IntegerField(default=1, help_text='客户在小程序下单时该技能最少需要选择的人数', verbose_name='最低下单人数'),
        ),
    ]
