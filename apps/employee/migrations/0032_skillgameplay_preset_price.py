from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0031_skillgameplay_preset_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillgameplay',
            name='preset_price',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                verbose_name='预制单项目价格'
            ),
        ),
    ]
