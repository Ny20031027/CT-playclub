from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User, Department


class EmployeeTag(BaseModel):
    name = models.CharField(max_length=50, unique=True, verbose_name='标签名称')
    color = models.CharField(max_length=20, default='#1890ff', verbose_name='标签颜色')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_tag'
        verbose_name = '打手标签'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class EmployeeSkill(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='技能名称')
    category = models.CharField(max_length=50, blank=True, verbose_name='分类')
    game_category = models.ForeignKey(
        'wx.GameCategory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills', verbose_name='游戏分类'
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价(元/小时)')
    icon = models.ImageField(upload_to='skills/', blank=True, verbose_name='图标')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_skill'
        verbose_name = '打手技能'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class SkillLevel(BaseModel):
    """技能段位 — 每个技能可自定义多个段位"""
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.CASCADE,
                              related_name='levels', verbose_name='所属技能')
    name = models.CharField(max_length=50, verbose_name='段位名称')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='时薪(元/小时)')
    sort = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'emp_skill_level'
        verbose_name = '技能段位'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return f"{self.skill.name} - {self.name}"


class Employee(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee',
                                verbose_name='关联用户')
    employee_no = models.CharField(max_length=50, unique=True, verbose_name='工号')
    real_name = models.CharField(max_length=100, verbose_name='真实姓名')
    nickname = models.CharField(max_length=100, blank=True, verbose_name='艺名')
    phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')
    avatar = models.CharField(max_length=500, blank=True, verbose_name='头像')
    gender = models.CharField(max_length=10, choices=[
        ('male', '男'),
        ('female', '女'),
        ('unknown', '未知'),
    ], default='unknown', verbose_name='性别')
    age = models.IntegerField(default=18, verbose_name='年龄')
    birthday = models.DateField(null=True, blank=True, verbose_name='生日')
    id_card = models.CharField(max_length=30, blank=True, verbose_name='身份证号')
    id_card_verified = models.BooleanField(default=False, verbose_name='实名认证')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='employees', verbose_name='所属部门')
    level = models.CharField(max_length=20, default='normal', choices=[
        ('new', '新人'),
        ('normal', '普通'),
        ('silver', '白银'),
        ('gold', '黄金'),
        ('diamond', '钻石'),
        ('king', '王者'),
    ], verbose_name='等级')
    level_num = models.IntegerField(default=0, verbose_name='等级数值')
    status = models.CharField(max_length=20, default='idle', choices=[
        ('idle', '空闲中'),
        ('busy', '接单中'),
        ('offline', '离线'),
        ('rest', '休息'),
        ('leave', '请假'),
    ], verbose_name='接单状态')
    online_status = models.BooleanField(default=False, verbose_name='在线状态')
    skills = models.ManyToManyField(EmployeeSkill, through='EmployeeSkillRelation',
                                    related_name='employees', verbose_name='技能')
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees',
                                  verbose_name='标签')
    intro = models.TextField(blank=True, verbose_name='个人简介')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0,
                                 verbose_name='评分')
    order_count = models.IntegerField(default=0, verbose_name='接单总数')
    total_duration = models.IntegerField(default=0, verbose_name='总时长(分钟)')
    commission_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             verbose_name='佣金余额(可提现)')
    join_date = models.DateField(null=True, blank=True, verbose_name='入职日期')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户行')
    bank_card = models.CharField(max_length=50, blank=True, verbose_name='银行卡号')
    alipay = models.CharField(max_length=100, blank=True, verbose_name='支付宝')
    wechat = models.CharField(max_length=100, blank=True, verbose_name='微信号')
    qq = models.CharField(max_length=50, blank=True, verbose_name='QQ号')
    sort = models.IntegerField(default=0, verbose_name='排序')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'emp_employee'
        verbose_name = '打手'
        verbose_name_plural = verbose_name
        ordering = ['sort', '-created_at']

    def __str__(self):
        return self.nickname or self.real_name


class EmployeeSkillRelation(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='skill_relations', verbose_name='打手')
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.CASCADE,
                              related_name='employee_relations', verbose_name='技能')
    skill_level = models.ForeignKey(SkillLevel, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='employee_relations', verbose_name='段位')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价(元/小时)')

    class Meta:
        db_table = 'emp_skill_relation'
        verbose_name = '陪玩师技能关系'
        verbose_name_plural = verbose_name
        unique_together = ['employee', 'skill']

    def __str__(self):
        return f"{self.employee} - {self.skill}"


class EmployeeWallet(BaseModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE,
                                    related_name='wallet', verbose_name='打手')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  verbose_name='余额')
    frozen_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                        verbose_name='冻结金额')
    total_income = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       verbose_name='累计收入')
    total_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                         verbose_name='累计提现')

    class Meta:
        db_table = 'emp_wallet'
        verbose_name = '打手钱包'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.employee} - 钱包"


class EmployeeContract(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='contracts', verbose_name='打手')
    contract_no = models.CharField(max_length=50, unique=True, verbose_name='合同编号')
    contract_type = models.CharField(max_length=20, default='employment', choices=[
        ('employment', '劳动合同'),
        ('cooperation', '合作协议'),
        ('parttime', '兼职协议'),
    ], verbose_name='合同类型')
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    status = models.CharField(max_length=20, default='active', choices=[
        ('active', '生效中'),
        ('expired', '已到期'),
        ('terminated', '已终止'),
    ], verbose_name='合同状态')
    file = models.FileField(upload_to='contracts/', blank=True, verbose_name='合同文件')
    salary_type = models.CharField(max_length=20, default='commission', choices=[
        ('fixed', '固定工资'),
        ('commission', '提成'),
        ('mix', '底薪+提成'),
    ], verbose_name='薪资类型')
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                      verbose_name='底薪')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=50,
                                          verbose_name='提成比例(%)')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'emp_contract'
        verbose_name = '打手合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.contract_no


class EmployeeStatus(BaseModel):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE,
                                    related_name='status_detail', verbose_name='打手')
    last_active = models.DateTimeField(auto_now=True, verbose_name='最后活跃时间')
    last_order_time = models.DateTimeField(null=True, blank=True, verbose_name='最后接单时间')
    today_orders = models.IntegerField(default=0, verbose_name='今日订单数')
    today_duration = models.IntegerField(default=0, verbose_name='今日时长(分钟)')
    today_income = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       verbose_name='今日收入')
    device = models.CharField(max_length=50, blank=True, verbose_name='设备信息')
    login_ip = models.CharField(max_length=50, blank=True, verbose_name='登录IP')

    class Meta:
        db_table = 'emp_status'
        verbose_name = '打手状态'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.employee} - 状态"


class Team(BaseModel):
    """打手组队"""
    name = models.CharField(max_length=100, verbose_name='队伍名称')
    leader = models.ForeignKey(Employee, on_delete=models.CASCADE,
                               related_name='led_teams', verbose_name='队长')
    status = models.BooleanField(default=True, verbose_name='状态')
    max_members = models.IntegerField(default=5, verbose_name='最大人数')

    class Meta:
        db_table = 'emp_team'
        verbose_name = '打手组队'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.leader.nickname}"

    @property
    def member_count(self):
        return self.members.filter(status='active').count()


class TeamMember(BaseModel):
    """组队成员"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE,
                             related_name='members', verbose_name='队伍')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='team_memberships', verbose_name='打手')
    status = models.CharField(max_length=20, default='active', choices=[
        ('active', '正常'),
        ('invited', '已邀请待确认'),
        ('left', '已退出'),
    ], verbose_name='状态')

    class Meta:
        db_table = 'emp_team_member'
        verbose_name = '组队成员'
        verbose_name_plural = verbose_name
        unique_together = ['team', 'employee']

    def __str__(self):
        return f"{self.team.name} - {self.employee.nickname}"
