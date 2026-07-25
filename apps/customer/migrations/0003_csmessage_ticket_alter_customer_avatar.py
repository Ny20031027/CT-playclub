from django.db import migrations, models
import django.db.models.deletion


def ensure_csmessage_ticket_column(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'cs_message'
              AND COLUMN_NAME = 'ticket_id'
            """
        )
        exists = cursor.fetchone()[0] > 0
        if exists:
            cursor.execute("ALTER TABLE `cs_message` MODIFY COLUMN `ticket_id` bigint NULL")
        else:
            cursor.execute("ALTER TABLE `cs_message` ADD COLUMN `ticket_id` bigint NULL")


class Migration(migrations.Migration):
    dependencies = [
        ('customer', '0002_customerservice_csmessage'),
        ('order', '0013_order_assigned_employee_alter_ordercomment_employee_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='csmessage',
                    name='ticket',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cs_messages', to='order.supportticket', verbose_name='鍏宠仈宸ュ崟'),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_csmessage_ticket_column, migrations.RunPython.noop),
            ],
        ),
        migrations.AlterField(
            model_name='customer',
            name='avatar',
            field=models.CharField(blank=True, max_length=500, verbose_name='澶村儚'),
        ),
    ]
