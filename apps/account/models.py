from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.common.models import BaseModel


class Department(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='部门名称')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name='上级部门')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sys_department'
        verbose_name = '部门'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Role(BaseModel):
    name = models.CharField(max_length=100, unique=True, verbose_name='角色名称')
    code = models.CharField(max_length=100, unique=True, verbose_name='角色编码')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')
    permissions = models.ManyToManyField('Permission', blank=True, related_name='roles',
                                         verbose_name='权限')
    data_scope = models.CharField(max_length=20, default='all',
                                  choices=[
                                      ('all', '全部数据'),
                                      ('dept', '本部门数据'),
                                      ('dept_and_children', '本部门及以下数据'),
                                      ('self', '仅本人数据'),
                                  ], verbose_name='数据权限范围')

    class Meta:
        db_table = 'sys_role'
        verbose_name = '角色'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Permission(BaseModel):
    name = models.CharField(max_length=100, verbose_name='权限名称')
    code = models.CharField(max_length=200, unique=True, verbose_name='权限标识')
    type = models.CharField(max_length=20,
                            choices=[
                                ('menu', '菜单'),
                                ('button', '按钮'),
                                ('api', '接口'),
                            ], verbose_name='类型')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='children', verbose_name='上级权限')
    path = models.CharField(max_length=500, blank=True, verbose_name='路由地址')
    component = models.CharField(max_length=500, blank=True, verbose_name='组件路径')
    icon = models.CharField(max_length=100, blank=True, verbose_name='图标')
    sort = models.IntegerField(default=0, verbose_name='排序')
    visible = models.BooleanField(default=True, verbose_name='是否显示')
    status = models.BooleanField(default=True, verbose_name='状态')
    remark = models.CharField(max_length=500, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sys_permission'
        verbose_name = '权限'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class User(AbstractUser, BaseModel):
    IDENTITY_ROLE_CODES = ('customer', 'dasher', 'cs')
    IDENTITY_ROLE_PRIORITY = ('cs', 'dasher', 'customer')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    avatar = models.ImageField(upload_to='avatars/', blank=True, verbose_name='头像')
    nickname = models.CharField(max_length=100, blank=True, verbose_name='昵称')
    gender = models.CharField(max_length=10, choices=[
        ('male', '男'),
        ('female', '女'),
        ('unknown', '未知'),
    ], default='unknown', verbose_name='性别')
    wx_openid = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name='微信openid')
    wx_unionid = models.CharField(max_length=100, blank=True, null=True, verbose_name='微信unionid')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='users', verbose_name='部门')
    roles = models.ManyToManyField(Role, blank=True, related_name='users', verbose_name='角色')
    is_online = models.BooleanField(default=False, verbose_name='是否在线')
    last_login_ip = models.CharField(max_length=50, blank=True, verbose_name='最后登录IP')

    class Meta:
        db_table = 'sys_user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.username

    def get_role_codes(self):
        return list(self.roles.filter(status=True, is_deleted=False).values_list('code', flat=True))

    def get_primary_identity_code(self, customer=None, employee=None):
        role_codes = [code for code in self.get_role_codes() if code in self.IDENTITY_ROLE_CODES]
        for code in self.IDENTITY_ROLE_PRIORITY:
            if code in role_codes:
                return code

        if employee is None:
            try:
                employee = self.employee
            except Exception:
                employee = None
        if employee:
            return 'dasher'

        if customer is None:
            try:
                customer = self.customer
            except Exception:
                customer = None
        if customer:
            try:
                customer.cs_profile
                return 'cs'
            except Exception:
                return 'customer'

        return 'customer'

    def get_user_permissions(self):
        perms = set()
        for role in self.roles.filter(status=True, is_deleted=False):
            for perm in role.permissions.filter(status=True, is_deleted=False):
                perms.add(perm.code)
        return perms

    def get_user_menus(self):
        menu_ids = set()
        for role in self.roles.filter(status=True, is_deleted=False):
            for perm in role.permissions.filter(type='menu', status=True, is_deleted=False, visible=True):
                menu_ids.add(perm.id)
        return Permission.objects.filter(id__in=menu_ids).order_by('sort', 'id')


class LoginLog(BaseModel):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='login_logs', verbose_name='用户')
    username = models.CharField(max_length=150, blank=True, verbose_name='用户名')
    ip = models.CharField(max_length=50, blank=True, verbose_name='登录IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='用户代理')
    status = models.BooleanField(default=True, verbose_name='登录状态')
    message = models.CharField(max_length=500, blank=True, verbose_name='提示信息')
    login_time = models.DateTimeField(auto_now_add=True, verbose_name='登录时间')

    class Meta:
        db_table = 'sys_login_log'
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.username} - {self.ip}"
