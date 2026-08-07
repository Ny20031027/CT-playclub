from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User
from apps.employee.models import Employee


class WxUser(BaseModel):
    """微信小程序用户"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wx_user',
                                null=True, blank=True, verbose_name='关联用户')
    openid = models.CharField(max_length=100, unique=True, verbose_name='openid')
    union_id = models.CharField(max_length=100, blank=True, verbose_name='unionid')
    session_key = models.CharField(max_length=200, blank=True, verbose_name='session_key')
    nickname = models.CharField(max_length=100, blank=True, verbose_name='昵称')
    avatar = models.CharField(max_length=500, blank=True, verbose_name='头像')
    gender = models.IntegerField(default=0, verbose_name='性别 0未知 1男 2女')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    last_login = models.DateTimeField(null=True, blank=True, verbose_name='最后登录时间')

    class Meta:
        db_table = 'wx_user'
        verbose_name = '小程序用户'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.nickname or self.openid


class Follow(BaseModel):
    """用户关注打手关系"""
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_relations',
                                 verbose_name='关注者(用户)')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='follower_relations',
                                 verbose_name='被关注者(打手)')

    class Meta:
        db_table = 'wx_follow'
        verbose_name = '关注关系'
        verbose_name_plural = verbose_name
        unique_together = [('follower', 'employee')]
        ordering = ['-created_at']

    def __str__(self):
        follower_name = getattr(self.follower, 'nickname', '') or getattr(getattr(self.follower, 'wx_user', None), 'nickname', '')
        return f"{follower_name or self.follower_id} 关注 {self.employee.nickname or self.employee_id}"

    def save(self, *args, **kwargs):
        created = self._state.adding
        super().save(*args, **kwargs)
        if created:
            Employee.objects.filter(pk=self.employee_id).update(fans_count=models.F('fans_count') + 1)

    def delete(self, *args, **kwargs):
        employee_id = self.employee_id
        super().delete(*args, **kwargs)
        Employee.objects.filter(pk=employee_id).update(fans_count=models.F('fans_count') - 1)
        # 防止负数
        Employee.objects.filter(pk=employee_id, fans_count__lt=0).update(fans_count=0)


class Banner(BaseModel):
    """首页轮播图"""
    title = models.CharField(max_length=200, blank=True, verbose_name='标题')
    image = models.CharField(max_length=500, verbose_name='图片URL')
    link_url = models.CharField(max_length=500, blank=True, verbose_name='跳转链接')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'wx_banner'
        verbose_name = '轮播图'
        verbose_name_plural = verbose_name
        ordering = ['sort', '-created_at']

    def __str__(self):
        return self.title or f'Banner {self.id}'


class Announcement(BaseModel):
    """首页公告"""
    title = models.CharField(max_length=200, verbose_name='标题')
    content = models.TextField(verbose_name='内容')
    type = models.CharField(max_length=20, default='info', choices=[
        ('info', '通知'),
        ('activity', '活动'),
        ('rule', '规则'),
    ], verbose_name='类型')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'wx_announcement'
        verbose_name = '公告'
        verbose_name_plural = verbose_name
        ordering = ['sort', '-created_at']

    def __str__(self):
        return self.title


class GameCategory(BaseModel):
    """游戏分类"""
    name = models.CharField(max_length=100, verbose_name='分类名称')
    icon = models.CharField(max_length=500, blank=True, verbose_name='图标URL')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'wx_game_category'
        verbose_name = '游戏分类'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name


class GameBanner(BaseModel):
    """游戏分类轮播图"""
    game = models.ForeignKey(GameCategory, on_delete=models.CASCADE, related_name='banners', verbose_name='游戏分类')
    title = models.CharField(max_length=200, blank=True, verbose_name='标题')
    image = models.CharField(max_length=500, verbose_name='图片URL')
    link_url = models.CharField(max_length=500, blank=True, verbose_name='跳转链接')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'wx_game_banner'
        verbose_name = '游戏轮播图'
        verbose_name_plural = verbose_name
        ordering = ['game__id', 'sort', '-created_at']

    def __str__(self):
        return self.title or f'GameBanner {self.id}'


class Gift(BaseModel):
    """礼物"""
    name = models.CharField(max_length=100, verbose_name='礼物名称')
    icon = models.CharField(max_length=500, verbose_name='礼物图标')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='价格')
    sort = models.IntegerField(default=0, verbose_name='排序')
    status = models.BooleanField(default=True, verbose_name='状态')

    class Meta:
        db_table = 'wx_gift'
        verbose_name = '礼物'
        verbose_name_plural = verbose_name
        ordering = ['sort', 'id']

    def __str__(self):
        return self.name
