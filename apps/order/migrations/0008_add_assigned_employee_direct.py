# 直接添加 assigned_employee_id 列
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE ord_order ADD COLUMN IF NOT EXISTS assigned_employee_id int NULL",
                "ALTER TABLE ord_order ADD CONSTRAINT fk_assigned_employee FOREIGN KEY (assigned_employee_id) REFERENCES employee_employee(id) ON DELETE SET NULL",
            ],
            reverse_sql=[
                "ALTER TABLE ord_order DROP FOREIGN KEY IF EXISTS fk_assigned_employee",
                "ALTER TABLE ord_order DROP COLUMN IF EXISTS assigned_employee_id",
            ],
        ),
    ]
