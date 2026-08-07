from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0024_employee_voice_duration_employee_voice_intro'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employee',
            name='voice_intro',
            field=models.URLField(blank=True, default='', max_length=500, null=True, verbose_name='语音介绍'),
        ),
    ]
