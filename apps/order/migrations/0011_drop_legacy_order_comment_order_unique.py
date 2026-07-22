from django.db import migrations


def drop_legacy_order_unique(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT INDEX_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ord_order_comment'
              AND NON_UNIQUE = 0
              AND INDEX_NAME <> 'PRIMARY'
            GROUP BY INDEX_NAME
            HAVING COUNT(*) = 1
               AND MAX(CASE WHEN COLUMN_NAME = 'order_id' THEN 1 ELSE 0 END) = 1
            """
        )
        for (index_name,) in cursor.fetchall():
            cursor.execute(f"ALTER TABLE ord_order_comment DROP INDEX `{index_name}`")


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0010_ordercomment_multi_person'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_order_unique, migrations.RunPython.noop),
    ]
