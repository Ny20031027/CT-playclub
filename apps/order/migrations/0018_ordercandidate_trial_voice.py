from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0017_order_chat_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordercandidate',
            name='trial_voice',
            field=models.CharField(blank=True, max_length=500, verbose_name='试音语音URL'),
        ),
        migrations.AddField(
            model_name='ordercandidate',
            name='trial_voice_duration',
            field=models.IntegerField(default=0, verbose_name='试音语音时长(秒)'),
        ),
        migrations.AddField(
            model_name='ordercandidate',
            name='trial_voice_upload_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='试音上传文件ID'),
        ),
    ]
