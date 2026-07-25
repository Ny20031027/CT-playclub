from django.db import migrations, models
import django.db.models.deletion


def ensure_ordercomment_member_column(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ord_order_comment'
              AND COLUMN_NAME = 'member_id'
            """
        )
        exists = cursor.fetchone()[0] > 0
        if exists:
            cursor.execute("ALTER TABLE `ord_order_comment` MODIFY COLUMN `member_id` bigint NULL")
        else:
            cursor.execute("ALTER TABLE `ord_order_comment` ADD COLUMN `member_id` bigint NULL")


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0006_order_leader'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='ordercomment',
                    name='order',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='comments',
                        to='order.order',
                        verbose_name='璁㈠崟',
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='ordercomment',
                    name='member',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='comments',
                        to='order.ordermember',
                        verbose_name='璁㈠崟鎴愬憳',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(ensure_ordercomment_member_column, migrations.RunPython.noop),
            ],
        ),
    ]
