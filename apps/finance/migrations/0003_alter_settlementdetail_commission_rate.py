from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('finance', '0002_alter_salary_employee_and_more')]

    operations = [
        migrations.AlterField(
            model_name='settlementdetail',
            name='commission_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=80,
                max_digits=5,
                verbose_name='打手结算比例(%)',
            ),
        ),
    ]
