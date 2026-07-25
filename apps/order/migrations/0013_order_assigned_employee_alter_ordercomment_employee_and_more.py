from django.db import migrations, models
import django.db.models.deletion


def ensure_order_assigned_employee_column(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ord_order'
              AND COLUMN_NAME = 'assigned_employee_id'
            """
        )
        exists = cursor.fetchone()[0] > 0
        if exists:
            cursor.execute("ALTER TABLE `ord_order` MODIFY COLUMN `assigned_employee_id` bigint NULL")
        else:
            cursor.execute("ALTER TABLE `ord_order` ADD COLUMN `assigned_employee_id` bigint NULL")


class Migration(migrations.Migration):
    dependencies = [
        ('employee', '0013_alter_employee_gender'),
        ('order', '0012_supportticket'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='order',
                    name='assigned_employee',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='assigned_orders',
                        to='employee.employee',
                        verbose_name='assigned_employee',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_order_assigned_employee_column, migrations.RunPython.noop),
            ],
        ),
        migrations.AlterField(
            model_name='ordercomment',
            name='employee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='comments',
                to='employee.employee',
                verbose_name='comment_employee',
            ),
        ),
        migrations.AlterField(
            model_name='ordermember',
            name='employee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='order_members',
                to='employee.employee',
                verbose_name='member_employee',
            ),
        ),
    ]
