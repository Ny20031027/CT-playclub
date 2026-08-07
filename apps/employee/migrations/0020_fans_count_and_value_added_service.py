# Generated manually on 2026-08-07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0019_add_gender_price_delta_and_allowed_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='fans_count',
            field=models.IntegerField(default=0, verbose_name='粉丝数'),
        ),
        migrations.CreateModel(
            name='ValueAddedService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='软删除标记')),
                ('name', models.CharField(max_length=80, verbose_name='名称')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='说明')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='单价(元/单位)')),
                ('sort', models.IntegerField(default=0, verbose_name='排序')),
                ('status', models.BooleanField(default=True, verbose_name='状态')),
                ('gameplay', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                               related_name='value_added_services', to='employee.skillgameplay',
                                               verbose_name='所属玩法')),
            ],
            options={
                'verbose_name': '增值服务',
                'verbose_name_plural': '增值服务',
                'db_table': 'emp_gameplay_value_added',
                'ordering': ['sort', 'id'],
                'unique_together': {('gameplay', 'name')},
            },
        ),
    ]