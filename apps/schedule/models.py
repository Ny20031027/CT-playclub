from django.db import models
from apps.common.models import BaseModel
from apps.employee.models import Employee
from apps.account.models import User, Department


class Shift(BaseModel):
    name = models.CharField(max_length=50, unique=True, verbose_name='班次名称')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    type = models.CharField(max_length=20, default='normal', choices=[
        ('morning', '早班'),
        ('noon', '午班'),
        ('evening', '晚班'),
        ('night', '夜班'),
        ('normal', '正常班'),
        ('custom', '自定义'),
    ], verbose_name='班次类型')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sch_shift'
        verbose_name = '班次'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'start_time']

    def __str__(self):
        return self.name


class Schedule(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='schedules', verbose_name='陪玩师')
    date = models.DateField(verbose_name='日期')
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='schedules', verbose_name='班次')
    start_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.TimeField(null=True, blank=True, verbose_name='结束时间')
    type = models.CharField(max_length=20, default='work', choices=[
        ('work', '上班'),
        ('rest', '休息'),
        ('leave', '请假'),
        ('business', '出差'),
        ('overtime', '加班'),
    ], verbose_name='排班类型')
    status = models.CharField(max_length=20, default='scheduled', choices=[
        ('scheduled', '已排班'),
        ('checked_in', '已签到'),
        ('checked_out', '已签退'),
        ('absent', '旷工'),
        ('cancelled', '已取消'),
    ], verbose_name='状态')
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name='签到时间')
    check_out_time = models.DateTimeField(null=True, blank=True, verbose_name='签退时间')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='created_schedules', verbose_name='创建人')

    class Meta:
        db_table = 'sch_schedule'
        verbose_name = '排班'
        verbose_name_plural = verbose_name
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']

    def __str__(self):
        return f"{self.employee} - {self.date}"


class Leave(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='leaves', verbose_name='陪玩师')
    leave_type = models.CharField(max_length=20, default='personal', choices=[
        ('personal', '事假'),
        ('sick', '病假'),
        ('annual', '年假'),
        ('marriage', '婚假'),
        ('maternity', '产假'),
        ('other', '其他'),
    ], verbose_name='请假类型')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    duration = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                   verbose_name='时长(天)')
    reason = models.TextField(verbose_name='请假原因')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('cancelled', '已取消'),
    ], verbose_name='状态')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='approved_leaves', verbose_name='审核人')
    approve_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    approve_remark = models.CharField(max_length=500, blank=True, verbose_name='审核备注')

    class Meta:
        db_table = 'sch_leave'
        verbose_name = '请假'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} - {self.leave_type}"


class Attendance(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='attendances', verbose_name='陪玩师')
    date = models.DateField(verbose_name='日期')
    check_in_time = models.DateTimeField(null=True, blank=True, verbose_name='签到时间')
    check_out_time = models.DateTimeField(null=True, blank=True, verbose_name='签退时间')
    work_duration = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                        verbose_name='工作时长(小时)')
    status = models.CharField(max_length=20, default='normal', choices=[
        ('normal', '正常'),
        ('late', '迟到'),
        ('early', '早退'),
        ('absent', '旷工'),
        ('leave', '请假'),
        ('rest', '休息'),
    ], verbose_name='考勤状态')
    late_minutes = models.IntegerField(default=0, verbose_name='迟到分钟数')
    early_minutes = models.IntegerField(default=0, verbose_name='早退分钟数')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')
    check_in_ip = models.CharField(max_length=50, blank=True, verbose_name='签到IP')
    check_out_ip = models.CharField(max_length=50, blank=True, verbose_name='签退IP')

    class Meta:
        db_table = 'sch_attendance'
        verbose_name = '考勤'
        verbose_name_plural = verbose_name
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']

    def __str__(self):
        return f"{self.employee} - {self.date}"


class Booking(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='bookings', verbose_name='陪玩师')
    customer = models.ForeignKey('customer.Customer', on_delete=models.CASCADE,
                                 related_name='bookings', null=True, blank=True,
                                 verbose_name='客户')
    date = models.DateField(verbose_name='预约日期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    duration = models.IntegerField(default=0, verbose_name='时长(分钟)')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待确认'),
        ('confirmed', '已确认'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
        ('timeout', '已超时'),
    ], verbose_name='状态')
    skill = models.ForeignKey('employee.EmployeeSkill', on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='bookings',
                              verbose_name='技能')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sch_booking'
        verbose_name = '预约'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} - {self.date}"


class CSSchedule(BaseModel):
    """客服排班（模板排班，设置一次后每天沿用）"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='cs_schedules', verbose_name='客服人员')
    day_of_week = models.IntegerField(choices=[
        (0, '周一'),
        (1, '周二'),
        (2, '周三'),
        (3, '周四'),
        (4, '周五'),
        (5, '周六'),
        (6, '周日'),
    ], verbose_name='星期')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    status = models.BooleanField(default=True, verbose_name='启用')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sch_cs_schedule'
        verbose_name = '客服排班'
        verbose_name_plural = verbose_name
        unique_together = ['employee', 'day_of_week']
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.employee} - 周{self.day_of_week + 1} {self.start_time}-{self.end_time}"
