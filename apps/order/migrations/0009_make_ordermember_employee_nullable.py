# 将 OrderMember.employee 列改为允许 NULL
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE ord_ordermember MODIFY COLUMN employee_id int NULL",
            reverse_sql="ALTER TABLE ord_ordermember MODIFY COLUMN employee_id int NOT NULL",
        ),
    ]
