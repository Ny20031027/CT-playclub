from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User
from apps.employee.models import Employee


class Wallet(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet',
                                null=True, blank=True, verbose_name='用户')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  verbose_name='余额')
    frozen_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='冻结金额')
    total_income = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='累计收入')
    total_expense = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='累计支出')
    type = models.CharField(max_length=20, default='platform', choices=[
        ('platform', '平台账户'),
        ('user', '用户账户'),
        ('employee', '陪玩师账户'),
    ], verbose_name='账户类型')

    class Meta:
        db_table = 'fin_wallet'
        verbose_name = '钱包'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.get_type_display()} - 钱包"


class Transaction(BaseModel):
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                               related_name='transactions', null=True, blank=True,
                               verbose_name='钱包')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='transactions', verbose_name='陪玩师')
    order_no = models.CharField(max_length=50, blank=True, verbose_name='关联订单号')
    transaction_no = models.CharField(max_length=50, unique=True, verbose_name='流水号')
    type = models.CharField(max_length=20, choices=[
        ('income', '收入'),
        ('expense', '支出'),
        ('freeze', '冻结'),
        ('unfreeze', '解冻'),
        ('transfer', '转账'),
    ], verbose_name='流水类型')
    category = models.CharField(max_length=50, blank=True, verbose_name='分类')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额')
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='交易后余额')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='operated_transactions', verbose_name='操作人')
    source = models.CharField(max_length=50, blank=True, verbose_name='来源')

    class Meta:
        db_table = 'fin_transaction'
        verbose_name = '财务流水'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.transaction_no


class Settlement(BaseModel):
    settlement_no = models.CharField(max_length=50, unique=True, verbose_name='结算单号')
    type = models.CharField(max_length=20, default='daily', choices=[
        ('daily', '日结'),
        ('weekly', '周结'),
        ('monthly', '月结'),
        ('manual', '手动结算'),
    ], verbose_name='结算类型')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待结算'),
        ('processing', '结算中'),
        ('completed', '已结算'),
        ('failed', '结算失败'),
    ], verbose_name='结算状态')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='结算总额')
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           verbose_name='总提成')
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='总利润')
    order_count = models.IntegerField(default=0, verbose_name='订单数')
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='settlements', verbose_name='操作人')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fin_settlement'
        verbose_name = '结算单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.settlement_no


class SettlementDetail(BaseModel):
    settlement = models.ForeignKey(Settlement, on_delete=models.CASCADE,
                                   related_name='details', verbose_name='结算单')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='settlement_details', verbose_name='陪玩师')
    order_count = models.IntegerField(default=0, verbose_name='订单数')
    total_duration = models.IntegerField(default=0, verbose_name='总时长(分钟)')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='订单总额')
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                            verbose_name='提成金额')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=50,
                                          verbose_name='提成比例(%)')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待结算'),
        ('completed', '已结算'),
    ], verbose_name='状态')

    class Meta:
        db_table = 'fin_settlement_detail'
        verbose_name = '结算明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f"{self.settlement.settlement_no} - {self.employee.nickname}"


class Salary(BaseModel):
    salary_no = models.CharField(max_length=50, unique=True, verbose_name='工资单号')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='salaries', verbose_name='陪玩师')
    month = models.CharField(max_length=7, verbose_name='月份(YYYY-MM)')
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                      verbose_name='底薪')
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='提成')
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                verbose_name='奖金')
    deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                    verbose_name='扣款')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='实发工资')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待发放'),
        ('processing', '发放中'),
        ('paid', '已发放'),
        ('cancelled', '已取消'),
    ], verbose_name='状态')
    pay_time = models.DateTimeField(null=True, blank=True, verbose_name='发放时间')
    pay_method = models.CharField(max_length=20, default='bank', choices=[
        ('bank', '银行卡'),
        ('alipay', '支付宝'),
        ('wechat', '微信'),
        ('cash', '现金'),
    ], verbose_name='发放方式')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='salaries', verbose_name='操作人')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fin_salary'
        verbose_name = '工资单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        unique_together = ['employee', 'month']

    def __str__(self):
        return self.salary_no


class Withdraw(BaseModel):
    withdraw_no = models.CharField(max_length=50, unique=True, verbose_name='提现单号')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='withdrawals', verbose_name='陪玩师')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='提现金额')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                              verbose_name='手续费')
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name='实际到账金额')
    withdraw_method = models.CharField(max_length=20, default='bank', choices=[
        ('bank', '银行卡'),
        ('alipay', '支付宝'),
        ('wechat', '微信'),
    ], verbose_name='提现方式')
    account_name = models.CharField(max_length=100, blank=True, verbose_name='账户名称')
    account_no = models.CharField(max_length=100, blank=True, verbose_name='账号')
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', '待审核'),
        ('approved', '审核通过'),
        ('rejected', '审核拒绝'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ], verbose_name='状态')
    apply_time = models.DateTimeField(auto_now_add=True, verbose_name='申请时间')
    audit_time = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    auditor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='audited_withdrawals', verbose_name='审核人')
    audit_remark = models.CharField(max_length=500, blank=True, verbose_name='审核备注')
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'fin_withdraw'
        verbose_name = '提现申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.withdraw_no
