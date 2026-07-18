from django.db import models
from apps.common.models import BaseModel


class DailyStat(BaseModel):
    date = models.DateField(unique=True, verbose_name='日期')
    total_orders = models.IntegerField(default=0, verbose_name='订单总数')
    completed_orders = models.IntegerField(default=0, verbose_name='完成订单数')
    cancelled_orders = models.IntegerField(default=0, verbose_name='取消订单数')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='总营收')
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='退款金额')
    net_income = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     verbose_name='净收入')
    new_customers = models.IntegerField(default=0, verbose_name='新增客户数')
    total_customers = models.IntegerField(default=0, verbose_name='客户总数')
    active_employees = models.IntegerField(default=0, verbose_name='活跃陪玩师数')
    total_duration = models.IntegerField(default=0, verbose_name='总服务时长(分钟)')
    avg_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           verbose_name='客单价')

    class Meta:
        db_table = 'stat_daily'
        verbose_name = '日统计'
        verbose_name_plural = verbose_name
        ordering = ['-date']

    def __str__(self):
        return str(self.date)


class MonthlyStat(BaseModel):
    year = models.IntegerField(verbose_name='年')
    month = models.IntegerField(verbose_name='月')
    total_orders = models.IntegerField(default=0, verbose_name='订单总数')
    completed_orders = models.IntegerField(default=0, verbose_name='完成订单数')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='总营收')
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='退款金额')
    net_income = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     verbose_name='净收入')
    new_customers = models.IntegerField(default=0, verbose_name='新增客户数')
    total_duration = models.IntegerField(default=0, verbose_name='总服务时长(分钟)')

    class Meta:
        db_table = 'stat_monthly'
        verbose_name = '月统计'
        verbose_name_plural = verbose_name
        unique_together = ['year', 'month']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.year}-{self.month:02d}"


class EmployeeRank(BaseModel):
    date = models.DateField(verbose_name='日期')
    period = models.CharField(max_length=20, default='daily', choices=[
        ('daily', '日'),
        ('weekly', '周'),
        ('monthly', '月'),
    ], verbose_name='周期')
    employee = models.ForeignKey('employee.Employee', on_delete=models.CASCADE,
                                 related_name='ranks', verbose_name='陪玩师')
    order_count = models.IntegerField(default=0, verbose_name='订单数')
    total_duration = models.IntegerField(default=0, verbose_name='总时长(分钟)')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='总金额')
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0,
                                     verbose_name='平均评分')
    rank = models.IntegerField(default=0, verbose_name='排名')

    class Meta:
        db_table = 'stat_employee_rank'
        verbose_name = '陪玩师排行'
        verbose_name_plural = verbose_name
        ordering = ['-date', 'rank']

    def __str__(self):
        return f"{self.date} - {self.employee.nickname}"
