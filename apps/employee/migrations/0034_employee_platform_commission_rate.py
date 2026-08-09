from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('employee', '0033_gameplaypresetitem')]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='platform_commission_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=20,
                max_digits=5,
                validators=[
                    MinValueValidator(Decimal('0.00')),
                    MaxValueValidator(Decimal('100.00')),
                ],
                verbose_name='平台抽成比例(%)',
            ),
        ),
    ]
