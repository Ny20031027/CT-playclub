# 修改 OrderComment 为支持多人订单评价
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordercomment',
            name='order',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='order.order', verbose_name='订单'),
        ),
        migrations.AddField(
            model_name='ordercomment',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='order.ordermember', verbose_name='订单成员'),
        ),
    ]
