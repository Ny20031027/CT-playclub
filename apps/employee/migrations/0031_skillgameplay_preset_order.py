from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0030_add_star_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillgameplay',
            name='order_mode',
            field=models.CharField(
                choices=[('custom', '选配单'), ('preset', '预制单')],
                default='custom', max_length=20, verbose_name='下单模式'
            ),
        ),
        migrations.AddField(
            model_name='skillgameplay',
            name='display_image',
            field=models.CharField(blank=True, max_length=500, verbose_name='预制单显示图片'),
        ),
        migrations.AddField(
            model_name='skillgameplay',
            name='preset_content',
            field=models.TextField(blank=True, verbose_name='预制单项目内容'),
        ),
        migrations.AddField(
            model_name='skillgameplay',
            name='preset_remark',
            field=models.CharField(blank=True, max_length=500, verbose_name='预制单项目备注'),
        ),
    ]
