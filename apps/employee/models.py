from decimal import Decimal

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
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


class GameRank(BaseModel):
    """A rank ladder entry owned by one game category."""
    game_category = models.ForeignKey(
        'wx.GameCategory', on_delete=models.CASCADE,
        related_name='ranks', verbose_name='游戏分类'
    )
    name = models.CharField(max_length=50, verbose_name='段位名称')
    sort = models.IntegerField(default=0, verbose_name='段位顺序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_game_rank'
        verbose_name = '游戏段位'
        verbose_name_plural = verbose_name
        ordering = ['game_category_id', 'sort', 'id']
        unique_together = [('game_category', 'name')]

    def __str__(self):
        return f'{self.game_category.name} - {self.name}'


class EmployeeSkill(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='技能名称')
    category = models.CharField(max_length=50, blank=True, verbose_name='分类')
    game_category = models.ForeignKey(
        'wx.GameCategory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills', verbose_name='游戏分类'
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价(元/小时)')
    icon = models.CharField(max_length=500, blank=True, verbose_name='图标URL')
    required_rank = models.ForeignKey(
        GameRank, on_delete=models.PROTECT, null=True, blank=True,
        related_name='skills', verbose_name='所需段位'
    )
    assignment_mode = models.CharField(max_length=20, default='manual', choices=[
        ('rank_auto', '达到段位自动拥有'),
        ('manual', '管理员手动添加'),
    ], verbose_name='授予方式')
    pricing_unit = models.CharField(max_length=20, default='hour', choices=[
        ('hour', '每小时'),
        ('round', '每局'),
    ], verbose_name='计价单位')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    skill_type = models.CharField(max_length=20, default='secondary', choices=[
        ('primary', '主技能'),
        ('secondary', '副技能'),
    ], verbose_name='技能类型')
    min_people = models.IntegerField(default=1, verbose_name='最低下单人数',
                                     help_text='客户在小程序下单时该技能最少需要选择的人数')

    description = models.TextField(blank=True, verbose_name='技能介绍')
    trial_mode = models.CharField(max_length=20, default='optional', choices=[
        ('disabled', '不支持试音'),
        ('optional', '可选试音'),
        ('required', '必须试音'),
    ], verbose_name='试音模式')
    order_notice = models.TextField(blank=True, verbose_name='下单须知')
    remark_placeholder = models.CharField(
        max_length=200, blank=True, default='选填，不超过30个字', verbose_name='备注提示'
    )
    self_service_enabled = models.BooleanField(default=False, verbose_name='启用自助下单')

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


class SkillGameplay(BaseModel):
    """A sellable gameplay under a skill."""
    ORDER_MODE_CHOICES = [
        ('custom', '选配单'),
        ('preset', '预制单'),
    ]

    skill = models.ForeignKey(
        EmployeeSkill, on_delete=models.CASCADE,
        related_name='self_service_gameplays', verbose_name='所属技能'
    )
    order_mode = models.CharField(
        max_length=20, choices=ORDER_MODE_CHOICES, default='custom',
        verbose_name='下单模式'
    )
    name = models.CharField(max_length=100, verbose_name='玩法名称')
    description = models.CharField(max_length=500, blank=True, verbose_name='玩法说明')
    display_image = models.CharField(max_length=500, blank=True, verbose_name='预制单显示图片')
    preset_content = models.TextField(blank=True, verbose_name='预制单项目内容')
    preset_remark = models.CharField(max_length=500, blank=True, verbose_name='预制单项目备注')
    preset_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='预制单项目价格'
    )
    difficulty_enabled = models.BooleanField(default=False, verbose_name='启用难度')
    gender_limit = models.CharField(max_length=20, default='unlimited', choices=[
        ('unlimited', '不限（不加价）'), ('male_only', '只男（固定）'), ('female_only', '只女（固定）'),
        ('optional', '性别可选（加价）'),
    ], verbose_name='服务者性别')
    male_price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='选男加价')
    female_price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='选女加价')
    companion_mode = models.CharField(max_length=20, default='single', choices=[
        ('single', '单陪'), ('double', '双陪'), ('both', '单陪和双陪'),
    ], verbose_name='陪玩类型')
    settlement_unit = models.CharField(max_length=20, default='hour', choices=[
        ('round', '局'), ('hour', '小时'),
    ], verbose_name='结算单位')
    min_quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1, verbose_name='最低购买量')
    quantity_step = models.DecimalField(max_digits=8, decimal_places=2, default=1, verbose_name='购买步长')
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='基础单价')
    remark_required = models.BooleanField(default=False, verbose_name='必须填写备注')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_skill_gameplay'
        ordering = ['sort', 'id']
        unique_together = [('skill', 'name')]

    def __str__(self):
        return f"{self.skill.name} - {self.name}"


class GameplayPresetItem(BaseModel):
    """A fixed-price preset order offered under one gameplay."""
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE,
        related_name='preset_items', verbose_name='所属玩法'
    )
    name = models.CharField(max_length=100, verbose_name='项目名称')
    display_image = models.CharField(max_length=500, blank=True, verbose_name='显示图片')
    content = models.TextField(blank=True, verbose_name='项目内容')
    remark = models.CharField(max_length=500, blank=True, verbose_name='项目备注')
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='项目价格'
    )
    required_people = models.PositiveIntegerField(
        default=1, verbose_name='所需人数', help_text='该预制单下单时锁定的人数，最低为1'
    )
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_preset_item'
        ordering = ['sort', 'id']
        unique_together = [('gameplay', 'name')]

    def __str__(self):
        return f"{self.gameplay.name} - {self.name}"


class GameplayDifficulty(BaseModel):
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE, related_name='difficulties', verbose_name='所属玩法'
    )
    name = models.CharField(max_length=50, verbose_name='难度名称')
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='加价')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_difficulty'
        ordering = ['sort', 'id']
        unique_together = [('gameplay', 'name')]


class GameplayLevelOption(BaseModel):
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE, related_name='level_options', verbose_name='所属玩法'
    )
    name = models.CharField(max_length=50, verbose_name='等级名称')
    description = models.CharField(max_length=200, blank=True, verbose_name='等级说明')
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='加价')
    is_recommended = models.BooleanField(default=False, verbose_name='推荐')
    allowed_services = models.JSONField(default=list, blank=True, verbose_name='允许的服务名称（空=全部）')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_level'
        ordering = ['sort', 'id']
        unique_together = [('gameplay', 'name')]


class GameplayService(BaseModel):
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE, related_name='services', verbose_name='所属玩法'
    )
    name = models.CharField(max_length=80, verbose_name='服务名称')
    description = models.CharField(max_length=200, blank=True, verbose_name='服务说明')
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='加价')
    is_recommended = models.BooleanField(default=False, verbose_name='推荐')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_service'
        ordering = ['sort', 'id']
        unique_together = [('gameplay', 'name')]


class GameplayPriceRule(BaseModel):
    """Exact price override for an option combination."""
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE, related_name='price_rules', verbose_name='所属玩法'
    )
    difficulty_name = models.CharField(max_length=50, blank=True, verbose_name='难度')
    level_name = models.CharField(max_length=50, blank=True, verbose_name='等级')
    service_name = models.CharField(max_length=80, blank=True, verbose_name='服务')
    gender_requirement = models.CharField(max_length=20, default='any', choices=[
        ('any', '不限'), ('male', '男'), ('female', '女'),
    ], verbose_name='性别要求')
    companion_type = models.CharField(max_length=20, default='single', choices=[
        ('single', '单陪'), ('double', '双陪'),
    ], verbose_name='陪玩类型')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='组合单价')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_price_rule'
        ordering = ['id']
        unique_together = [(
            'gameplay', 'difficulty_name', 'level_name', 'service_name',
            'gender_requirement', 'companion_type'
        )]


class ValueAddedService(BaseModel):
    """玩法附加项目，管理员可选配置，用户可选非强制"""
    gameplay = models.ForeignKey(
        SkillGameplay, on_delete=models.CASCADE, related_name='value_added_services', verbose_name='所属玩法'
    )
    name = models.CharField(max_length=80, verbose_name='名称')
    description = models.CharField(max_length=200, blank=True, verbose_name='说明')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价(元/单位)')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_gameplay_value_added'
        verbose_name = '附加项目'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
        unique_together = [('gameplay', 'name')]

    def __str__(self):
        return f"{self.gameplay.name} - {self.name}"


class AddonValueAddedService(BaseModel):
    """附加项下独立配置的附加增值服务。"""
    addon = models.ForeignKey(
        ValueAddedService, on_delete=models.CASCADE,
        related_name='value_added_services', verbose_name='所属附加项'
    )
    name = models.CharField(max_length=80, verbose_name='附加增值名称')
    description = models.CharField(max_length=200, blank=True, verbose_name='说明')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价(元/单位)')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_addon_value_added'
        verbose_name = '附加项增值服务'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
        unique_together = [('addon', 'name')]

    def __str__(self):
        return f"{self.addon.name} - {self.name}"


class ServiceValueAdded(BaseModel):
    """服务类型增值服务，每个服务类型独立设置，管理员可选配置，用户可选非强制"""
    service = models.ForeignKey(
        GameplayService, on_delete=models.CASCADE, related_name='value_added_services', verbose_name='所属服务'
    )
    name = models.CharField(max_length=80, verbose_name='名称')
    description = models.CharField(max_length=200, blank=True, verbose_name='说明')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='单价(元/单位)')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'emp_service_value_added'
        verbose_name = '增值服务'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']
        unique_together = [('service', 'name')]

    def __str__(self):
        return f"{self.service.name} - {self.name}"


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
    assessment_mode = models.CharField(max_length=10, choices=[
        ('single', '单考'),
        ('double', '双考'),
    ], default='single', verbose_name='考核模式')
    status = models.CharField(max_length=20, default='idle', choices=[
        ('idle', '空闲中'),
        ('busy', '接单中'),
        ('offline', '离线'),
        ('rest', '休息'),
        ('leave', '请假'),
    ], verbose_name='接单状态')
    work_status = models.CharField(max_length=20, default='off_duty', choices=[
        ('on_duty', '上班'),
        ('off_duty', '下班'),
    ], verbose_name='上下班状态')
    online_status = models.BooleanField(default=False, verbose_name='在线状态')
    skills = models.ManyToManyField(EmployeeSkill, through='EmployeeSkillRelation',
                                    related_name='employees', verbose_name='技能')
    game_categories = models.ManyToManyField(
        'wx.GameCategory', blank=True,
        related_name='employees', verbose_name='游戏分类'
    )
    tags = models.ManyToManyField(EmployeeTag, blank=True, related_name='employees',
                                  verbose_name='标签')
    intro = models.TextField(blank=True, verbose_name='个人简介')
    # 语音文件由统一上传服务托管，这里只保存可访问 URL，不再让 FileField
    # 误以为 Django 需要二次保存文件。
    voice_intro = models.URLField(max_length=500, null=True, blank=True, default='',
                                  verbose_name='语音介绍')
    voice_duration = models.IntegerField(default=0, verbose_name='语音时长(秒)')
    photos = models.JSONField(default=list, blank=True, verbose_name='照片墙')
    is_star = models.BooleanField(default=False, verbose_name='明星打手')
    star_sort = models.IntegerField(default=0, verbose_name='明星排序')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0,
                                 verbose_name='评分')
    order_count = models.IntegerField(default=0, verbose_name='接单总数')
    total_duration = models.IntegerField(default=0, verbose_name='总时长(分钟)')
    fans_count = models.IntegerField(default=0, verbose_name='粉丝数')
    commission_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                             verbose_name='佣金余额(可提现)')
    platform_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=20,
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        verbose_name='平台抽成比例(%)'
    )
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


class EmployeeGameRank(BaseModel):
    """The rank manually assigned to an employee for one game category."""
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='game_rank_relations', verbose_name='打手'
    )
    game_category = models.ForeignKey(
        'wx.GameCategory', on_delete=models.CASCADE,
        related_name='employee_rank_relations', verbose_name='游戏分类'
    )
    rank = models.ForeignKey(
        GameRank, on_delete=models.PROTECT,
        related_name='employee_relations', verbose_name='当前段位'
    )

    class Meta:
        db_table = 'emp_employee_game_rank'
        verbose_name = '打手游戏段位'
        verbose_name_plural = verbose_name
        unique_together = [('employee', 'game_category')]

    def __str__(self):
        return f'{self.employee} - {self.game_category.name}: {self.rank.name}'


class EmployeeSkillRelation(BaseModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='skill_relations', verbose_name='打手')
    skill = models.ForeignKey(EmployeeSkill, on_delete=models.CASCADE,
                              related_name='employee_relations', verbose_name='技能')
    skill_level = models.ForeignKey(SkillLevel, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='employee_relations', verbose_name='段位')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                     verbose_name='单价(元/小时)')
    skill_type = models.CharField(max_length=20, default='secondary', choices=[
        ('primary', '主技能'),
        ('secondary', '副技能'),
    ], verbose_name='技能类型')
    assignment_source = models.CharField(max_length=20, default='manual', choices=[
        ('rank_auto', '段位自动授予'),
        ('manual', '管理员手动授予'),
    ], verbose_name='授予来源')
    price_overridden = models.BooleanField(default=False, verbose_name='使用专属价格')
    is_enabled = models.BooleanField(default=True, verbose_name='打手已开启')

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


class EmployeeAttendance(BaseModel):
    """打手打卡记录"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                 related_name='attendance_records', verbose_name='打手')
    punch_type = models.CharField(max_length=20, choices=[
        ('clock_in', '上班打卡'),
        ('clock_out', '下班打卡'),
    ], verbose_name='打卡类型')
    punch_time = models.DateTimeField(auto_now_add=True, verbose_name='打卡时间')
    location = models.CharField(max_length=200, blank=True, verbose_name='打卡地点')
    ip_address = models.CharField(max_length=50, blank=True, verbose_name='IP地址')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'emp_attendance'
        verbose_name = '打手打卡记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.nickname} - {self.get_punch_type_display()} - {self.punch_time.strftime('%Y-%m-%d %H:%M')}"
