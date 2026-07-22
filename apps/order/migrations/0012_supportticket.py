from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
        ('customer', '0001_initial'),
        ('employee', '0001_initial'),
        ('order', '0011_drop_legacy_order_comment_order_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('ticket_no', models.CharField(max_length=50, unique=True, verbose_name='工单号')),
                ('title', models.CharField(max_length=200, verbose_name='工单标题')),
                ('description', models.TextField(blank=True, verbose_name='工单描述')),
                ('status', models.CharField(choices=[('open', '待处理'), ('in_progress', '处理中'), ('closed', '已关闭')], default='open', max_length=20, verbose_name='工单状态')),
                ('order_snapshot', models.JSONField(default=dict, verbose_name='订单快照')),
                ('handle_remark', models.TextField(blank=True, verbose_name='处理备注')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='关闭时间')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_tickets', to='customer.customer', verbose_name='客户')),
                ('employee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_tickets', to='employee.employee', verbose_name='打手')),
                ('handler', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='handled_tickets', to='account.user', verbose_name='处理人')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tickets', to='order.order', verbose_name='订单')),
            ],
            options={
                'verbose_name': '售后工单',
                'verbose_name_plural': '售后工单',
                'db_table': 'ord_support_ticket',
                'ordering': ['-created_at'],
            },
        ),
    ]
