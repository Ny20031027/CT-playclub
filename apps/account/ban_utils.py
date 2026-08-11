"""封禁 / 冻结 公共工具"""
import datetime

from django.utils import timezone


def apply_ban(user, duration_type, duration=None, reason=''):
    """对用户执行封禁。
    duration_type: hours|days|forever
    duration: 时长数值（hours/days 时有效）
    """
    user.is_banned = True
    user.ban_reason = (reason or '')[:200]
    if duration_type == 'forever':
        user.ban_until = None
    else:
        hours = int(duration or 1) * (24 if duration_type == 'days' else 1)
        if hours < 1:
            hours = 1
        user.ban_until = timezone.now() + datetime.timedelta(hours=hours)
    user.save(update_fields=['is_banned', 'ban_until', 'ban_reason'])


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
        'permanent': user.ban_until is None,
        'ban_reason': user.ban_reason or '',
    }
