from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0021_add_completion_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='tip_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='小费金额'),
        ),
    ]
