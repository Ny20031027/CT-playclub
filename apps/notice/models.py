from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User
from apps.employee.models import Employee


class Notice(BaseModel):
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    type = models.CharField(max_length=20, default='system', choices=[
        ('system', '系统通知'),
        ('order', '订单通知'),
        ('finance', '财务通知'),
        ('activity', '活动通知'),
        ('other', '其他'),
    ], verbose_name='通知类型')
    level = models.CharField(max_length=20, default='normal', choices=[
        ('info', '普通'),
        ('warning', '警告'),
        ('danger', '重要'),
        ('success', '成功'),
    ], verbose_name='级别')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='sent_notices', verbose_name='发送人')
    target_type = models.CharField(max_length=20, default='all', choices=[
        ('all', '全部用户'),
        ('role', '指定角色'),
        ('employee', '指定陪玩师'),
        ('user', '指定用户'),
    ], verbose_name='目标类型')
    target_ids = models.TextField(blank=True, verbose_name='目标ID列表')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    is_published = models.BooleanField(default=True, verbose_name='是否发布')
    publish_time = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    jump_url = models.CharField(max_length=500, blank=True, verbose_name='跳转链接')
    extra = models.TextField(blank=True, verbose_name='附加数据')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'notice_notice'
        verbose_name = '通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class UserNotice(BaseModel):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE,
                               related_name='user_notices', verbose_name='通知')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='notices', verbose_name='用户')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    read_time = models.DateTimeField(null=True, blank=True, verbose_name='读取时间')

    class Meta:
        db_table = 'notice_user_notice'
        verbose_name = '用户通知'
        verbose_name_plural = verbose_name
        unique_together = ['notice', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.notice.title}"


class EmployeeNotice(BaseModel):
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE,
                               related_name='employee_notices', verbose_name='通知')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='notices', verbose_name='陪玩师')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    read_time = models.DateTimeField(null=True, blank=True, verbose_name='读取时间')

    class Meta:
        db_table = 'notice_employee_notice'
        verbose_name = '陪玩师通知'
        verbose_name_plural = verbose_name
        unique_together = ['notice', 'employee']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} - {self.notice.title}"


class SmsLog(BaseModel):
    phone = models.CharField(max_length=20, verbose_name='手机号')
    content = models.TextField(verbose_name='内容')
    type = models.CharField(max_length=20, default='code', choices=[
        ('code', '验证码'),
        ('notice', '通知'),
        ('marketing', '营销'),
    ], verbose_name='类型')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待发送'),
        ('success', '发送成功'),
        ('failed', '发送失败'),
    ], verbose_name='状态')
    error_msg = models.CharField(max_length=500, blank=True, verbose_name='错误信息')
    send_time = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')

    class Meta:
        db_table = 'notice_sms_log'
        verbose_name = '短信发送记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.phone} - {self.type}"


class EmailLog(BaseModel):
    email = models.CharField(max_length=100, verbose_name='邮箱')
    subject = models.CharField(max_length=200, verbose_name='主题')
    content = models.TextField(verbose_name='内容')
    type = models.CharField(max_length=20, default='notice', choices=[
        ('notice', '通知'),
        ('marketing', '营销'),
        ('code', '验证码'),
    ], verbose_name='类型')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待发送'),
        ('success', '发送成功'),
        ('failed', '发送失败'),
    ], verbose_name='状态')
    error_msg = models.CharField(max_length=500, blank=True, verbose_name='错误信息')
    send_time = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')

    class Meta:
        db_table = 'notice_email_log'
        verbose_name = '邮件发送记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} - {self.subject}"
