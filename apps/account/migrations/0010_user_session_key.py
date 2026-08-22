from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0009_seed_user_management_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='session_key',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='当前登录会话标识'),
        ),
    ]
