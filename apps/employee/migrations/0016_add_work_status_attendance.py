from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0015_add_skill_min_people'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='work_status',
            field=models.CharField(
                choices=[('on_duty', '上班'), ('off_duty', '下班')],
                default='off_duty',
                max_length=20,
                verbose_name='上下班状态',
            ),
        ),
        migrations.CreateModel(
            name='EmployeeAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('punch_type', models.CharField(
                    choices=[('clock_in', '上班打卡'), ('clock_out', '下班打卡')],
                    max_length=20,
                    verbose_name='打卡类型',
                )),
                ('punch_time', models.DateTimeField(auto_now_add=True, verbose_name='打卡时间')),
                ('location', models.CharField(blank=True, max_length=200, verbose_name='打卡地点')),
                ('ip_address', models.CharField(blank=True, max_length=50, verbose_name='IP地址')),
                ('remark', models.CharField(blank=True, max_length=500, verbose_name='备注')),
                ('employee', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='attendance_records',
                    to='employee.employee',
                    verbose_name='打手',
                )),
            ],
            options={
                'verbose_name': '打手打卡记录',
                'verbose_name_plural': '打手打卡记录',
                'db_table': 'emp_attendance',
                'ordering': ['-created_at'],
            },
        ),
    ]
