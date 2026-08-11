from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('account', '0006_add_ban_freeze')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='auth_invalid_before',
            field=models.DateTimeField(blank=True, null=True, verbose_name='登录凭证失效时间'),
        ),
    ]
