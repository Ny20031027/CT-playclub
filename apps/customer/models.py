from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User


class CustomerLevel(BaseModel):
    name = models.CharField(max_length=50, unique=True, verbose_name='等级名称')
    level = models.IntegerField(unique=True, verbose_name='等级值')
    icon = models.ImageField(upload_to='customer_levels/', blank=True, verbose_name='图标')
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='最低消费金额')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=100,
                                   verbose_name='折扣比例(%)')
    color = models.CharField(max_length=20, default='#1890ff', verbose_name='等级颜色')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'cus_level'
        verbose_name = '客户等级'
        verbose_name_plural = verbose_name
        ordering = ['level', 'sort']

    def __str__(self):
        return self.name


class CustomerTag(BaseModel):
    name = models.CharField(max_length=50, unique=True, verbose_name='标签名称')
    color = models.CharField(max_length=20, default='#1890ff', verbose_name='标签颜色')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'cus_tag'
        verbose_name = '客户标签'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class Customer(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer',
                                null=True, blank=True, verbose_name='关联用户')
    nickname = models.CharField(max_length=100, verbose_name='昵称')
    avatar = models.CharField(max_length=500, blank=True, verbose_name='头像')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    email = models.EmailField(max_length=100, blank=True, verbose_name='邮箱')
    gender = models.CharField(max_length=10, choices=[
        ('male', '男'),
        ('female', '女'),
        ('unknown', '未知'),
    ], default='unknown', verbose_name='性别')
    age = models.IntegerField(null=True, blank=True, verbose_name='年龄')
    wechat = models.CharField(max_length=100, blank=True, verbose_name='微信号')
    qq = models.CharField(max_length=50, blank=True, verbose_name='QQ号')
    level = models.ForeignKey(CustomerLevel, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='customers', verbose_name='客户等级')
    tags = models.ManyToManyField(CustomerTag, blank=True, related_name='customers',
                                  verbose_name='标签')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='累计消费')
    total_orders = models.IntegerField(default=0, verbose_name='累计订单数')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  verbose_name='账户余额')
    status = models.BooleanField(default=True, verbose_name='状态')
    source = models.CharField(max_length=50, blank=True, verbose_name='来源渠道')
    first_order_date = models.DateTimeField(null=True, blank=True, verbose_name='首单时间')
    last_order_date = models.DateTimeField(null=True, blank=True, verbose_name='最后下单时间')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')
    address = models.CharField(max_length=500, blank=True, verbose_name='地址')

    class Meta:
        db_table = 'cus_customer'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.nickname


class Blacklist(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE,
                                 related_name='blacklist_records', verbose_name='客户')
    reason = models.CharField(max_length=500, verbose_name='拉黑原因')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='blacklist_ops', verbose_name='操作人')
    expire_time = models.DateTimeField(null=True, blank=True, verbose_name='到期时间')
    status = models.BooleanField(default=True, verbose_name='是否生效')

    class Meta:
        db_table = 'cus_blacklist'
        verbose_name = '黑名单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer} - 黑名单"


class CustomerConsumeRecord(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE,
                                 related_name='consume_records', verbose_name='客户')
    order_no = models.CharField(max_length=50, blank=True, verbose_name='订单号')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='消费金额')
    type = models.CharField(max_length=20, default='order', choices=[
        ('order', '订单消费'),
        ('recharge', '充值'),
        ('refund', '退款'),
        ('withdraw', '提现'),
        ('other', '其他'),
    ], verbose_name='类型')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'cus_consume_record'
        verbose_name = '消费记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer} - {self.amount}"


class CustomerService(BaseModel):
    """客服人员"""
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE,
                                    related_name='cs_profile', verbose_name='关联客户')
    status = models.CharField(max_length=20, default='online', choices=[
        ('online', '在线'),
        ('offline', '离线'),
        ('busy', '忙碌'),
    ], verbose_name='在线状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'cus_service'
        verbose_name = '客服人员'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.customer.nickname} - 客服"


class CSMessage(BaseModel):
    """客服消息"""
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE,
                                 related_name='cs_messages', verbose_name='客户')
    cs_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='cs_received_messages', verbose_name='客服')
    ticket = models.ForeignKey('order.SupportTicket', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='cs_messages', verbose_name='关联工单')
    content = models.TextField(verbose_name='消息内容')
    msg_type = models.CharField(max_length=20, default='text', choices=[
        ('text', '文本'),
        ('image', '图片'),
    ], verbose_name='消息类型')
    is_read = models.BooleanField(default=False, verbose_name='是否已读')
    sender_type = models.CharField(max_length=20, default='customer', choices=[
        ('customer', '客户'),
        ('cs', '客服'),
    ], verbose_name='发送者类型')

    class Meta:
        db_table = 'cs_message'
        verbose_name = '客服消息'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f"{self.customer.nickname} - {self.content[:20]}"
