# Generated manually on 2026-08-07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wx', '0002_add_game_banner'),
        ('employee', '0020_fans_count_and_value_added_service'),
        ('account', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Follow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='软删除标记')),
                ('follower', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name='following_relations', to='account.user',
                                               verbose_name='关注者(用户)')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name='follower_relations', to='employee.employee',
                                               verbose_name='被关注者(打手)')),
            ],
            options={
                'verbose_name': '关注关系',
                'verbose_name_plural': '关注关系',
                'db_table': 'wx_follow',
                'ordering': ['-created_at'],
                'unique_together': {('follower', 'employee')},
            },
        ),
    ]