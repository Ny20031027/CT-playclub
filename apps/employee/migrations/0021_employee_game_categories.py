from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wx', '0003_follow_relation'),
        ('employee', '0020_fans_count_and_value_added_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='game_categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='employees',
                to='wx.gamecategory',
                verbose_name='游戏分类'
            ),
        ),
    ]
