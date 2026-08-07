from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0021_employee_game_categories'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceValueAdded',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('name', models.CharField(max_length=80, verbose_name='名称')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='说明')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='单价(元/单位)')),
                ('sort', models.IntegerField(default=0, verbose_name='排序')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='value_added_services', to='employee.gameplayservice', verbose_name='所属服务')),
            ],
            options={
                'verbose_name': '增值服务',
                'verbose_name_plural': '增值服务',
                'db_table': 'emp_service_value_added',
                'ordering': ['sort', 'id'],
                'unique_together': {('service', 'name')},
            },
        ),
    ]
