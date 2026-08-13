from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0038_employee_quick_welcome_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='quick_welcome_messages',
            field=models.JSONField(blank=True, default=list, verbose_name='群聊快捷欢迎语列表'),
        ),
    ]
