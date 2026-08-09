from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_presets(apps, schema_editor):
    SkillGameplay = apps.get_model('employee', 'SkillGameplay')
    GameplayPresetItem = apps.get_model('employee', 'GameplayPresetItem')
    for gameplay in SkillGameplay.objects.filter(order_mode='preset', is_deleted=False):
        if not (gameplay.display_image or gameplay.preset_content or gameplay.preset_remark or gameplay.preset_price):
            continue
        GameplayPresetItem.objects.get_or_create(
            gameplay_id=gameplay.id,
            name=gameplay.name,
            defaults={
                'display_image': gameplay.display_image,
                'content': gameplay.preset_content,
                'remark': gameplay.preset_remark,
                'price': gameplay.preset_price,
                'sort': 0,
                'status': gameplay.status,
            },
        )


class Migration(migrations.Migration):
    dependencies = [('employee', '0032_skillgameplay_preset_price')]

    operations = [
        migrations.CreateModel(
            name='GameplayPresetItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('name', models.CharField(max_length=100, verbose_name='项目名称')),
                ('display_image', models.CharField(blank=True, max_length=500, verbose_name='显示图片')),
                ('content', models.TextField(blank=True, verbose_name='项目内容')),
                ('remark', models.CharField(blank=True, max_length=500, verbose_name='项目备注')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='项目价格')),
                ('sort', models.IntegerField(default=0, verbose_name='排序')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('gameplay', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='preset_items', to='employee.skillgameplay', verbose_name='所属玩法')),
            ],
            options={
                'db_table': 'emp_gameplay_preset_item',
                'ordering': ['sort', 'id'],
                'unique_together': {('gameplay', 'name')},
            },
        ),
        migrations.RunPython(migrate_legacy_presets, migrations.RunPython.noop),
    ]
