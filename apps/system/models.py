from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User


class Config(BaseModel):
    key = models.CharField(max_length=100, unique=True, verbose_name='配置键')
    value = models.TextField(blank=True, verbose_name='配置值')
    name = models.CharField(max_length=200, blank=True, verbose_name='配置名称')
    type = models.CharField(max_length=20, default='string', choices=[
        ('string', '字符串'),
        ('number', '数字'),
        ('boolean', '布尔值'),
        ('json', 'JSON'),
        ('text', '文本'),
    ], verbose_name='类型')
    group = models.CharField(max_length=50, default='basic', verbose_name='分组')
    sort = models.IntegerField(default=0, verbose_name='排序')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sys_config'
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name
        ordering = ['group', 'sort', 'key']

    def __str__(self):
        return f"{self.key} - {self.value}"


class Dictionary(BaseModel):
    name = models.CharField(max_length=100, verbose_name='字典名称')
    code = models.CharField(max_length=100, unique=True, verbose_name='字典编码')
    type = models.CharField(max_length=20, default='list', choices=[
        ('list', '列表'),
        ('tree', '树形'),
    ], verbose_name='类型')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sys_dictionary'
        verbose_name = '字典'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class DictionaryItem(BaseModel):
    dictionary = models.ForeignKey(Dictionary, on_delete=models.CASCADE,
                                   related_name='items', verbose_name='字典')
    label = models.CharField(max_length=100, verbose_name='标签')
    value = models.CharField(max_length=200, verbose_name='值')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name='上级')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    color = models.CharField(max_length=20, blank=True, verbose_name='颜色')
    css_class = models.CharField(max_length=100, blank=True, verbose_name='样式类')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sys_dictionary_item'
        verbose_name = '字典项'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
        unique_together = ['dictionary', 'value']

    def __str__(self):
        return f"{self.dictionary.name} - {self.label}"


class OperationLog(BaseModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='operation_logs', verbose_name='用户')
    username = models.CharField(max_length=150, blank=True, verbose_name='用户名')
    module = models.CharField(max_length=100, blank=True, verbose_name='模块')
    operation = models.CharField(max_length=100, blank=True, verbose_name='操作')
    method = models.CharField(max_length=10, blank=True, verbose_name='请求方法')
    path = models.CharField(max_length=500, blank=True, verbose_name='请求路径')
    ip = models.CharField(max_length=50, blank=True, verbose_name='IP地址')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='用户代理')
    params = models.TextField(blank=True, verbose_name='请求参数')
    result = models.TextField(blank=True, verbose_name='返回结果')
    status_code = models.IntegerField(default=200, verbose_name='状态码')
    duration = models.FloatField(default=0, verbose_name='耗时(秒)')

    class Meta:
        db_table = 'sys_operation_log'
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.operation}"


class ErrorLog(BaseModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='error_logs', verbose_name='用户')
    type = models.CharField(max_length=100, verbose_name='错误类型')
    message = models.TextField(verbose_name='错误信息')
    traceback = models.TextField(blank=True, verbose_name='堆栈信息')
    path = models.CharField(max_length=500, blank=True, verbose_name='请求路径')
    method = models.CharField(max_length=10, blank=True, verbose_name='请求方法')
    params = models.TextField(blank=True, verbose_name='请求参数')
    ip = models.CharField(max_length=50, blank=True, verbose_name='IP地址')

    class Meta:
        db_table = 'sys_error_log'
        verbose_name = '错误日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.type


class CSWelcomeConfig(BaseModel):
    """客服欢迎语配置"""
    welcome_text = models.TextField(blank=True, default='', verbose_name='欢迎语内容', help_text='客户进入客服聊天时自动发送的欢迎语')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'sys_cs_welcome_config'
        verbose_name = '客服欢迎语配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"欢迎语 - {self.welcome_text[:30]}"

    def save(self, *args, **kwargs):
        if not self.pk:
            try:
                CSWelcomeConfig.objects.all().delete()
            except Exception:
                pass
        super().save(*args, **kwargs)


class CSKeywordRule(BaseModel):
    """客服关键词自动回复规则"""
    keyword = models.CharField(max_length=200, verbose_name='关键词', help_text='触发自动回复的关键词')
    reply_text = models.TextField(verbose_name='回复内容', help_text='匹配关键词后自动回复的内容')
    match_type = models.CharField(max_length=20, default='contains', choices=[
        ('contains', '包含'),
        ('exact', '完全匹配'),
        ('startswith', '开头匹配'),
    ], verbose_name='匹配方式')
    sort = models.IntegerField(default=0, verbose_name='排序')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'sys_cs_keyword_rule'
        verbose_name = '客服关键词规则'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return f"{self.keyword} → {self.reply_text[:20]}"


class Coupon(BaseModel):
    """优惠券模板"""
    COUPON_TYPE_CHOICES = [
        ('discount', '减免券'),
    ]

    name = models.CharField(max_length=100, verbose_name='券名', help_text='如"七折券"')
    coupon_type = models.CharField(max_length=20, default='discount', choices=COUPON_TYPE_CHOICES,
                                   verbose_name='券类型')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=70.00,
                                        verbose_name='折扣比例(%)',
                                        help_text='如70表示打七折，实际支付金额 × 70%')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           verbose_name='最低订单金额',
                                           help_text='满多少元可用，0表示不限')
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name='最大优惠金额(元)',
                                              help_text='单次最多优惠多少元，0表示不限')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.CharField(max_length=500, blank=True, verbose_name='使用说明')

    class Meta:
        db_table = 'sys_coupon'
        verbose_name = '优惠券模板'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}（{self.discount_rate}%）"


class UserCoupon(BaseModel):
    """用户持有的优惠券"""
    customer = models.ForeignKey('customer.Customer', on_delete=models.CASCADE,
                                 related_name='coupons', verbose_name='客户')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE,
                               related_name='user_coupons', verbose_name='券模板')
    status = models.CharField(max_length=20, default='unused', choices=[
        ('unused', '未使用'),
        ('used', '已使用'),
        ('expired', '已过期'),
    ], verbose_name='状态')
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='使用时间')
    used_order_no = models.CharField(max_length=50, blank=True, verbose_name='使用订单号')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='过期时间')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='issued_coupons', verbose_name='发放人')

    class Meta:
        db_table = 'sys_user_coupon'
        verbose_name = '用户优惠券'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.nickname} - {self.coupon.name}"



