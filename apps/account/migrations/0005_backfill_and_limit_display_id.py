import secrets

from django.core.validators import RegexValidator
from django.db import migrations, models


def backfill_display_ids(apps, schema_editor):
    User = apps.get_model('account', 'User')
    users = list(User.objects.all().only('id', 'display_id'))
    used = {
        user.display_id for user in users
        if user.display_id and user.display_id.isdigit() and len(user.display_id) <= 9
    }
    for user in users:
        if user.display_id and user.display_id.isdigit() and len(user.display_id) <= 9:
            continue
        while True:
            candidate = str(100000000 + secrets.randbelow(900000000))
            if candidate not in used:
                used.add(candidate)
                user.display_id = candidate
                user.save(update_fields=['display_id'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0004_add_display_id'),
    ]

    operations = [
        migrations.RunPython(backfill_display_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='display_id',
            field=models.CharField(
                blank=True,
                max_length=9,
                null=True,
                unique=True,
                validators=[RegexValidator(r'^\d{1,9}$', '黑金ID只能包含1至9位数字')],
                verbose_name='黑金ID',
            ),
        ),
    ]
