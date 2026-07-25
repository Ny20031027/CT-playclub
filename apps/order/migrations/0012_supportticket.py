from django.db import migrations, models
import django.db.models.deletion

from apps.order.models import SupportTicket as CurrentSupportTicket


def ensure_support_ticket_table(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ord_support_ticket'
            """
        )
        exists = cursor.fetchone()[0] > 0
    if not exists:
        schema_editor.create_model(CurrentSupportTicket)


class Migration(migrations.Migration):
    dependencies = [
        ('account', '0001_initial'),
        ('customer', '0001_initial'),
        ('employee', '0001_initial'),
        ('order', '0011_drop_legacy_order_comment_order_unique'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='SupportTicket',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created_at')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated_at')),
                        ('is_deleted', models.BooleanField(default=False, verbose_name='is_deleted')),
                        ('ticket_no', models.CharField(max_length=50, unique=True, verbose_name='ticket_no')),
                        ('title', models.CharField(max_length=200, verbose_name='title')),
                        ('description', models.TextField(blank=True, verbose_name='description')),
                        ('status', models.CharField(
                            choices=[('open', 'open'), ('in_progress', 'in_progress'), ('closed', 'closed')],
                            default='open',
                            max_length=20,
                            verbose_name='status',
                        )),
                        ('order_snapshot', models.JSONField(default=dict, verbose_name='order_snapshot')),
                        ('handle_remark', models.TextField(blank=True, verbose_name='handle_remark')),
                        ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='closed_at')),
                        ('customer', models.ForeignKey(
                            on_delete=django.db.models.deletion.PROTECT,
                            related_name='support_tickets',
                            to='customer.customer',
                            verbose_name='customer',
                        )),
                        ('employee', models.ForeignKey(
                            blank=True,
                            null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='support_tickets',
                            to='employee.employee',
                            verbose_name='employee',
                        )),
                        ('handler', models.ForeignKey(
                            blank=True,
                            null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='handled_tickets',
                            to='account.user',
                            verbose_name='handler',
                        )),
                        ('order', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='tickets',
                            to='order.order',
                            verbose_name='order',
                        )),
                    ],
                    options={
                        'verbose_name': 'SupportTicket',
                        'verbose_name_plural': 'SupportTicket',
                        'db_table': 'ord_support_ticket',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_support_ticket_table, migrations.RunPython.noop),
            ],
        ),
    ]
