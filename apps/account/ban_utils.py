"""封禁 / 冻结 公共工具"""
import datetime

from django.utils import timezone


def apply_ban(user, duration_type, duration=None, reason=''):
    """对用户执行封禁。
    duration_type: hours|days|forever
    duration: 时长数值（hours/days 时有效）
    """
    if duration_type not in ('hours', 'days', 'forever'):
        raise ValueError('封禁时长类型无效')
    user.is_banned = True
    user.ban_reason = (reason or '')[:200]
    if duration_type == 'forever':
        user.ban_until = None
    else:
        try:
            duration_value = int(duration)
        except (TypeError, ValueError):
            raise ValueError('封禁时长必须是正整数')
        if duration_value < 1:
            raise ValueError('封禁时长必须大于0')
        hours = duration_value * (24 if duration_type == 'days' else 1)
        user.ban_until = timezone.now() + datetime.timedelta(hours=hours)
    # 记录凭证失效分界并更新在线状态。即使随后解封，封禁前签发的 JWT 也不能恢复使用。
    # JWT 的 iat 精度为秒；按秒保存边界，避免刚解封后新签发的 token
    # 因数据库微秒精度而被误判为旧 token。
    user.auth_invalid_before = timezone.now().replace(microsecond=0)
    user.is_online = False
    user.save(update_fields=[
        'is_banned', 'ban_until', 'ban_reason', 'auth_invalid_before', 'is_online'
    ])


def remove_ban(user):
    """解除封禁"""
    user.is_banned = False
    user.ban_until = None
    user.ban_reason = ''
    user.save(update_fields=['is_banned', 'ban_until', 'ban_reason'])


def ban_info(user):
    """返回封禁状态描述；到期自动解封"""
    active = user.is_banned_active()
    if not active:
        return {'is_banned': False, 'ban_until': None, 'ban_reason': ''}
    return {
        'is_banned': True,
        'ban_until': user.ban_until.isoformat() if user.ban_until else None,
        'ban_until_display': (
            timezone.localtime(user.ban_until).strftime('%Y-%m-%d %H:%M')
            if user.ban_until and timezone.is_aware(user.ban_until)
            else user.ban_until.strftime('%Y-%m-%d %H:%M') if user.ban_until else None
        ),
        'permanent': user.ban_until is None,
        'ban_reason': user.ban_reason or '',
    }


def ban_message(user):
    info = ban_info(user)
    if not info.get('is_banned'):
        return ''
    deadline = '永久封禁' if info.get('permanent') else f"封禁至 {info.get('ban_until_display')}"
    reason = f"，原因：{info.get('ban_reason')}" if info.get('ban_reason') else ''
    return f'账号已被封禁（{deadline}{reason}）'
