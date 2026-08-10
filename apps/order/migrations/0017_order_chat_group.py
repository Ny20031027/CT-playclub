from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('order', '0016_order_purchase_quantity_order_self_service_snapshot_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderChatGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('name', models.CharField(max_length=200, verbose_name='群名称')),
                ('expires_at', models.DateTimeField(verbose_name='到期时间')),
                ('is_active', models.BooleanField(default=True, verbose_name='有效')),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='chat_group', to='order.order', verbose_name='订单')),
            ],
            options={'db_table': 'ord_chat_group', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OrderChatMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('role', models.CharField(choices=[('customer', '客户'), ('dasher', '打手'), ('cs', '客服')], max_length=20)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='order.orderchatgroup')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_chat_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'ord_chat_member', 'unique_together': {('group', 'user')}},
        ),
        migrations.CreateModel(
            name='OrderChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('content', models.TextField(verbose_name='消息内容')),
                ('msg_type', models.CharField(choices=[('text', '文本'), ('system', '系统消息')], default='text', max_length=20)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='order.orderchatgroup')),
                ('sender', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_chat_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'ord_chat_message', 'ordering': ['created_at']},
        ),
    ]
