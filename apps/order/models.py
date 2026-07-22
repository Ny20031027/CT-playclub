from django.db import models
from apps.common.models import BaseModel
from apps.customer.models import Customer
from apps.employee.models import Employee, EmployeeSkill
from apps.account.models import User


class OrderStatus(models.TextChoices):
    PUBLISHED = 'published', '可领取'
    CLAIMED = 'claimed', '待开始'
    CONFIRMING = 'confirming', '待双方确认'
    IN_PROGRESS = 'in_progress', '进行中'
    COMPLETED = 'completed', '已结束'
    REVIEWED = 'reviewed', '已评价'
    CANCELLED = 'cancelled', '已取消'


class Order(BaseModel):
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT,
                                 related_name='orders', verbose_name='客户')
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.PROTECT,
                              related_name='orders', null=True, blank=True,
                              verbose_name='技能')
    status = models.CharField(max_length=20, choices=OrderStatus.choices,
                              default=OrderStatus.PUBLISHED, verbose_name='订单状态')
    title = models.CharField(max_length=200, blank=True, verbose_name='订单标题')
    order_type = models.CharField(max_length=20, default='single', choices=[
        ('single', '单人单'),
        ('multi', '多人单'),
        ('package', '套餐单'),
        ('self_service', '自助单'),
    ], verbose_name='订单类型')
    quantity = models.IntegerField(default=1, verbose_name='人数')
    locked_slots = models.IntegerField(default=0, verbose_name='已锁定席位')
    leader = models.ForeignKey('employee.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='led_orders', verbose_name='队长')
    assigned_employee = models.ForeignKey('employee.Employee', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='assigned_orders', verbose_name='预约打手')
    duration = models.IntegerField(default=0, verbose_name='时长(分钟)')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='订单总额')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name='优惠金额')
    # 双方确认状态
    customer_confirmed = models.BooleanField(default=False, verbose_name='客户已确认')
    dasher_confirmed = models.BooleanField(default=False, verbose_name='打手已确认')
    pay_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='实付金额')
    pay_method = models.CharField(max_length=20, default='balance', choices=[
        ('balance', '余额支付'),
        ('wechat', '微信支付'),
        ('alipay', '支付宝'),
        ('cash', '现金'),
        ('other', '其他'),
    ], verbose_name='支付方式')
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name='支付时间')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    assign_time = models.DateTimeField(null=True, blank=True, verbose_name='派单时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    cancel_time = models.DateTimeField(null=True, blank=True, verbose_name='取消时间')
    cancel_reason = models.CharField(max_length=500, blank=True, verbose_name='取消原因')
    transfer_reason = models.CharField(max_length=500, blank=True, verbose_name='转单原因')
    discount_reason = models.CharField(max_length=500, blank=True, verbose_name='免单原因')
    assigner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='assigned_orders', verbose_name='派单员')
    game_id = models.CharField(max_length=100, blank=True, verbose_name='游戏ID')
    game_name = models.CharField(max_length=100, blank=True, verbose_name='游戏名称')
    server = models.CharField(max_length=100, blank=True, verbose_name='区服')
    remark = models.TextField(blank=True, verbose_name='备注')
    customer_contact = models.CharField(max_length=100, blank=True, verbose_name='客户联系方式')
    platform = models.CharField(max_length=50, default='web', choices=[
        ('web', '网站'),
        ('wechat', '微信'),
        ('qq', 'QQ'),
        ('mini_program', '小程序'),
        ('other', '其他'),
    ], verbose_name='下单渠道')
    source = models.CharField(max_length=50, blank=True, verbose_name='来源')

    class Meta:
        db_table = 'ord_order'
        verbose_name = '订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.order_no

    @property
    def members(self):
        return self.order_members.all()

    @property
    def total_duration(self):
        return self.duration or 0


class OrderMember(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                              related_name='order_members', verbose_name='订单')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='order_members', verbose_name='陪玩师')
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='order_members', verbose_name='技能')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价')
    duration = models.IntegerField(default=0, verbose_name='时长(分钟)')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                 verbose_name='金额')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            verbose_name='提成金额')
    status = models.CharField(max_length=20, default='assigned', choices=[
        ('assigned', '已分配'),
        ('accepted', '已接单'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ], verbose_name='状态')
    accept_time = models.DateTimeField(null=True, blank=True, verbose_name='接单时间')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'ord_order_member'
        verbose_name = '订单陪玩'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f"{self.order.order_no} - {self.employee.nickname}"


class OrderPrice(BaseModel):
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.CASCADE,
                              related_name='prices', verbose_name='技能')
    level = models.CharField(max_length=20, default='normal', choices=[
        ('new', '新人'),
        ('normal', '普通'),
        ('silver', '白银'),
        ('gold', '黄金'),
        ('diamond', '钻石'),
        ('king', '王者'),
    ], verbose_name='陪玩师等级')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价(元/小时)')
    min_duration = models.IntegerField(default=1, verbose_name='最低时长(分钟)')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'ord_order_price'
        verbose_name = '订单价格'
        verbose_name_plural = verbose_name
        unique_together = ['skill', 'level']
        ordering = ['skill', 'level']

    def __str__(self):
        return f"{self.skill} - {self.level}"


class OrderComment(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                              related_name='comments', verbose_name='订单')
    member = models.ForeignKey('OrderMember', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='comments', verbose_name='订单成员')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT,
                                 related_name='comments', verbose_name='客户')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='comments', verbose_name='陪玩师')
    rating = models.IntegerField(default=5, verbose_name='评分(1-5)')
    content = models.TextField(blank=True, verbose_name='评价内容')
    tags = models.CharField(max_length=500, blank=True, verbose_name='评价标签')
    is_anonymous = models.BooleanField(default=False, verbose_name='是否匿名')
    images = models.TextField(blank=True, verbose_name='评价图片')
    reply = models.TextField(blank=True, verbose_name='商家回复')
    reply_time = models.DateTimeField(null=True, blank=True, verbose_name='回复时间')

    class Meta:
        db_table = 'ord_order_comment'
        verbose_name = '订单评价'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.order_no} - 评价"


class SupportTicket(BaseModel):
    """售后工单"""
    class TicketStatus(models.TextChoices):
        OPEN = 'open', '待处理'
        IN_PROGRESS = 'in_progress', '处理中'
        CLOSED = 'closed', '已关闭'

    ticket_no = models.CharField(max_length=50, unique=True, verbose_name='工单号')
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                              related_name='tickets', verbose_name='订单')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT,
                                 related_name='support_tickets', verbose_name='客户')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='support_tickets', verbose_name='打手')
    title = models.CharField(max_length=200, verbose_name='工单标题')
    description = models.TextField(blank=True, verbose_name='工单描述')
    status = models.CharField(max_length=20, choices=TicketStatus.choices,
                              default=TicketStatus.OPEN, verbose_name='工单状态')

    # 快照：下单时抓取的订单信息，防止后续修改导致工单信息失真
    order_snapshot = models.JSONField(default=dict, verbose_name='订单快照')

    handler = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='handled_tickets', verbose_name='处理人')
    handle_remark = models.TextField(blank=True, verbose_name='处理备注')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')

    class Meta:
        db_table = 'ord_support_ticket'
        verbose_name = '售后工单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_no} - {self.title}"


class OrderRefund(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,
                              related_name='refunds', verbose_name='订单')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT,
                                 related_name='refunds', verbose_name='客户')
    refund_no = models.CharField(max_length=50, unique=True, verbose_name='退款单号')
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                        verbose_name='退款金额')
    refund_reason = models.CharField(max_length=500, verbose_name='退款原因')
    refund_method = models.CharField(max_length=20, default='original', choices=[
        ('original', '原路退回'),
        ('balance', '退到余额'),
        ('cash', '现金'),
        ('other', '其他'),
    ], verbose_name='退款方式')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('completed', '已完成'),
    ], verbose_name='退款状态')
    auditor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='refund_approvals', verbose_name='审核人')
    audit_remark = models.CharField(max_length=500, blank=True, verbose_name='审核备注')
    audit_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    applicant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='refund_applications', verbose_name='申请人')

    class Meta:
        db_table = 'ord_order_refund'
        verbose_name = '订单退款'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.refund_no
