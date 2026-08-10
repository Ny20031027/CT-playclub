from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer', '0007_customer_coins'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerServiceConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('eligible_user_ids', models.JSONField(blank=True, default=list, verbose_name='可接入客服用户ID')),
                ('status', models.CharField(choices=[('waiting', '等待接入'), ('active', '处理中'), ('closed', '已结束')], default='waiting', max_length=20)),
                ('requested_at', models.DateTimeField(auto_now_add=True, verbose_name='请求时间')),
                ('accepted_at', models.DateTimeField(blank=True, null=True, verbose_name='接入时间')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='结束时间')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_conversations', to='customer.customer', verbose_name='客户')),
                ('handler', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='service_conversations', to=settings.AUTH_USER_MODEL, verbose_name='接入客服')),
            ],
            options={'db_table': 'cs_conversation', 'ordering': ['-requested_at']},
        ),
    ]
