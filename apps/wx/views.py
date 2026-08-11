import json
import re
import datetime
import requests
import warnings
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Sum, Count
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from urllib3.exceptions import InsecureRequestWarning
from apps.common.media import build_media_url
from apps.common.response import success_response, error_response
from apps.common.encoding_utils import fix_mojibake
from apps.common.viewsets import BaseModelViewSet
from apps.account.models import User
from apps.employee.models import (
    Employee, EmployeeGameRank, EmployeeSkill, EmployeeSkillRelation, EmployeeTag, SkillLevel,
    SkillGameplay, GameplayPresetItem, GameplayDifficulty, GameplayLevelOption, GameplayService,
    ValueAddedService, AddonValueAddedService, ServiceValueAdded,
)
from apps.order.models import (
    Order, OrderMember, OrderComment, OrderPrice, OrderStatus, SupportTicket, OrderCandidate,
    OrderChatGroup, OrderChatMember, OrderChatMessage,
)
from apps.order.comment_utils import create_order_comment_with_retry
from apps.order.services import (
    OrderCompletionError, complete_order_and_settle,
)
from apps.notice.models import Notice, UserNotice
from apps.system.agreements import get_agreement, get_agreements
from apps.system.recharge_offers import get_recharge_offers
from apps.finance.models import Wallet, Transaction
from apps.upload.models import UploadFile
from .models import WxUser, Banner, Announcement, GameCategory, Gift, GameBanner, Follow, GameAccount, DasherApplication, PreOrder
from .serializers import (
    WxUserSerializer, BannerSerializer, AnnouncementSerializer,
    GameCategorySerializer, GiftSerializer, GameBannerSerializer
)

import logging
logger = logging.getLogger(__name__)


class GameCategoryViewSet(BaseModelViewSet):
    """游戏分类管理（品类设置）"""
    queryset = GameCategory.objects.all()
    serializer_class = GameCategorySerializer
    filterset_fields = ['status']
    search_fields = ['name']
    ordering_fields = ['sort', 'id']
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return success_response({'results': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(self.get_serializer(instance).data)

# 微信小程序配置 - 需要在 settings.py 或环境变量中配置
WX_APPID = getattr(settings, 'WX_APPID', '')
WX_SECRET = getattr(settings, 'WX_SECRET', '')

ACTIVE_ORDER_MEMBER_STATUSES = ['accepted', 'in_progress']
FORMAL_ORDER_STATUSES = ['confirming', 'claimed', 'in_progress', 'completed', 'reviewed']


def _as_localtime(value):
    return timezone.localtime(value) if timezone.is_aware(value) else value


def _current_duty_cs_users(now=None):
    """返回当前排班时段内的客服用户，兼容跨午夜班次。"""
    from apps.schedule.models import CSSchedule
    from apps.customer.models import CustomerService

    local_now = _as_localtime(now or timezone.now())
    weekday = local_now.weekday()
    current_time = local_now.time().replace(tzinfo=None)
    schedules = CSSchedule.objects.filter(status=True).select_related('employee__user')
    employee_user_ids = []
    for schedule in schedules:
        same_day = schedule.day_of_week == weekday
        if schedule.start_time <= schedule.end_time:
            active = same_day and schedule.start_time <= current_time <= schedule.end_time
        else:
            previous_day = (weekday - 1) % 7
            active = (
                (same_day and current_time >= schedule.start_time) or
                (schedule.day_of_week == previous_day and current_time <= schedule.end_time)
            )
        if active and schedule.employee.user_id:
            employee_user_ids.append(schedule.employee.user_id)

    valid_ids = set(CustomerService.objects.filter(
        customer__user_id__in=employee_user_ids,
        is_deleted=False,
        customer__user__is_active=True,
    ).values_list('customer__user_id', flat=True))
    return list(User.objects.filter(id__in=valid_ids, is_active=True))


def _create_order_chat_group(order):
    """创建订单临时群，并将客户、全部接单打手和当班客服加入。"""
    group, created = OrderChatGroup.objects.get_or_create(
        order=order,
        defaults={
            'name': f'订单 {order.order_no} 服务群',
            'expires_at': timezone.now() + datetime.timedelta(hours=72),
            'is_active': True,
        },
    )
    if not created:
        return group

    members = []
    if order.customer.user_id:
        members.append((order.customer.user_id, 'customer'))
    dasher_ids = order.order_members.filter(
        is_deleted=False, status__in=['accepted', 'in_progress']
    ).values_list('employee__user_id', flat=True)
    members.extend((user_id, 'dasher') for user_id in dasher_ids if user_id)
    members.extend((user.id, 'cs') for user in _current_duty_cs_users())
    for user_id, role in dict(members).items():
        OrderChatMember.objects.get_or_create(group=group, user_id=user_id, defaults={'role': role})
    # 群组欢迎语：读取系统配置，未配置时使用默认文案
    group_welcome = ''
    try:
        from apps.system.models import Config
        cfg = Config.objects.filter(key='group_welcome_text', is_deleted=False).first()
        if cfg and cfg.value and cfg.value.strip():
            group_welcome = cfg.value.strip()
    except Exception:
        group_welcome = ''
    OrderChatMessage.objects.create(
        group=group,
        content=group_welcome or '订单已开始，客户、接单打手和当前值班客服已加入本群。本群将在72小时后自动删除。',
        msg_type='system',
    )
    return group


def _cs_message_has_ticket_column():
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'cs_message'
                  AND COLUMN_NAME = 'ticket_id'
            """)
            return cursor.fetchone()[0] > 0
    except Exception:
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'cs_message'
                  AND COLUMN_NAME = 'ticket_id'
            """)
            return cursor.fetchone()[0] > 0
    except Exception:
        return False


def _build_support_ticket_order_snapshot(order, customer=None):
    members_data = []
    for m in order.order_members.filter(is_deleted=False).select_related('employee', 'skill'):
        members_data.append({
            'employee_name': m.employee.nickname if m.employee else '',
            'skill_name': m.skill.name if m.skill else '',
            'unit_price': float(m.unit_price),
            'duration': m.duration,
            'amount': float(m.amount),
            'status': m.status,
        })

    return {
        'order_id': order.id,
        'order_no': order.order_no,
        'status': order.status,
        'status_display': order.get_status_display(),
        'order_type': order.order_type,
        'game_name': order.game_name,
        'server': order.server,
        'duration': order.duration,
        'quantity': order.quantity,
        'unit_price': float(order.unit_price),
        'total_amount': float(order.total_amount),
        'pay_amount': float(order.pay_amount),
        'pay_method': order.pay_method,
        'customer_name': customer.nickname if customer else (order.customer.nickname if order.customer else ''),
        'members': members_data,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'transfer_reason': order.transfer_reason or '',
    }


def _build_support_ticket_order_card(ticket):
    if not ticket:
        return None

    order = ticket.order
    snapshot = ticket.order_snapshot or {}
    order_id = order.id if order else snapshot.get('order_id')
    order_no = order.order_no if order else snapshot.get('order_no', '')
    status_display = order.get_status_display() if order else snapshot.get('status_display', '')
    game_name = order.game_name if order else snapshot.get('game_name', '')
    server = order.server if order else snapshot.get('server', '')
    pay_amount = float(order.pay_amount) if order else float(snapshot.get('pay_amount') or 0)
    total_amount = float(order.total_amount) if order else float(snapshot.get('total_amount') or 0)
    created_at = order.created_at.strftime('%Y-%m-%d %H:%M') if order else snapshot.get('created_at', '')

    return {
        'ticket_id': ticket.id,
        'ticket_no': ticket.ticket_no,
        'order_id': order_id,
        'order_no': order_no,
        'title': ticket.title,
        'status': order.status if order else snapshot.get('status', ''),
        'status_display': status_display,
        'game_name': game_name,
        'server': server,
        'pay_amount': pay_amount,
        'total_amount': total_amount,
        'created_at': created_at,
        'jump_url': f'/pages/order-detail/order-detail?id={order_id}' if order_id else '',
        'summary': f'{order_no} · {status_display}' if order_no else status_display,
    }


def _ensure_ticket_order_card_message(customer, ticket):
    if not customer or not ticket or not _cs_message_has_ticket_column():
        return None

    from apps.customer.models import CSMessage

    existing = CSMessage.objects.filter(
        customer=customer,
        ticket=ticket,
        msg_type='order_card',
        is_deleted=False,
    ).first()
    if existing:
        return existing

    return CSMessage.objects.create(
        customer=customer,
        cs_user=None,
        ticket=ticket,
        content='订单详情卡片',
        msg_type='order_card',
        sender_type='customer',
    )


def _serialize_cs_message(msg):
    cs_name = ''
    if msg.cs_user:
        cs_profile = getattr(msg.cs_user, 'cs_profile', None)
        if cs_profile:
            cs_name = cs_profile.customer.nickname

    order_card = None
    ticket = getattr(msg, 'ticket', None)
    if ticket:
        order_card = _build_support_ticket_order_card(ticket)

    return {
        'id': msg.id,
        'content': msg.content,
        'msg_type': msg.msg_type,
        'sender_type': msg.sender_type,
        'is_read': msg.is_read,
        'cs_name': cs_name,
        'ticket_id': ticket.id if ticket else None,
        'order_card': order_card,
        'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
    }


def is_default_nickname(nickname):
    if not nickname:
        return True
    nickname = str(nickname).strip()
    if nickname == '测试用户':
        return True
    return bool(re.fullmatch(r'用户[\w-]{1,12}', nickname))


def field_file_url(value):
    if not value:
        return ''
    value_str = str(value).strip()
    if value_str.startswith('http://') or value_str.startswith('https://'):
        return value_str
    return ''


def employee_avatar_url(employee):
    if not employee:
        return ''
    user = getattr(employee, 'user', None)
    candidates = [employee.avatar]
    try:
        if user:
            candidates.append(user.wx_user.avatar)
    except WxUser.DoesNotExist:
        pass
    except Exception:
        pass
    if user:
        candidates.append(user.avatar)

    for avatar in candidates:
        url = field_file_url(avatar)
        if url:
            return url
    return ''


def get_profile_wx_user(user):
    try:
        return user.wx_user
    except WxUser.DoesNotExist:
        return None


def get_related_profile_objects(user):
    objects = {'wx_user': None, 'customer': None, 'employee': None}
    try:
        objects['wx_user'] = user.wx_user
    except WxUser.DoesNotExist:
        pass
    try:
        objects['customer'] = user.customer
        if getattr(objects['customer'], 'is_deleted', False):
            objects['customer'] = None
    except Exception:
        pass
    try:
        objects['employee'] = user.employee
        if getattr(objects['employee'], 'is_deleted', False):
            objects['employee'] = None
    except Exception:
        pass
    return objects


def choose_display_nickname(user, wx_user=None, customer=None, employee=None, fallback=''):
    candidates = [
        wx_user.nickname if wx_user else '',
        user.nickname,
        employee.nickname if employee else '',
        customer.nickname if customer else '',
    ]
    for nickname in candidates:
        if nickname and not is_default_nickname(nickname):
            return nickname
    for nickname in candidates:
        if nickname:
            return nickname
    return fallback or f'用户{user.id}'


def sync_profile_tables(user, nickname=None, avatar=None, phone=None, gender=None):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'sync_profile_tables: user={user.id}, gender={gender}')
    
    user_fields = []
    if nickname and user.nickname != nickname:
        user.nickname = nickname
        user_fields.append('nickname')
    if avatar and str(user.avatar) != avatar:
        user.avatar = avatar
        user_fields.append('avatar')
    if phone and user.phone != phone:
        user.phone = phone
        user_fields.append('phone')
    if gender is not None and user.gender != gender:
        user.gender = gender
        user_fields.append('gender')
        logger.info(f'User gender updated to: {gender}')
    if user_fields:
        user.save(update_fields=user_fields)
        logger.info(f'User saved with fields: {user_fields}')

    wx_user = get_profile_wx_user(user)
    if wx_user:
        wx_fields = []
        if nickname and wx_user.nickname != nickname:
            wx_user.nickname = nickname
            wx_fields.append('nickname')
        if avatar and wx_user.avatar != avatar:
            wx_user.avatar = avatar
            wx_fields.append('avatar')
        if phone and wx_user.phone != phone:
            wx_user.phone = phone
            wx_fields.append('phone')
        if gender is not None:
            gender_value = {'male': 1, 'female': 2, 'unknown': 0}.get(gender)
            if gender_value is not None and wx_user.gender != gender_value:
                wx_user.gender = gender_value
                wx_fields.append('gender')
                logger.info(f'WxUser gender updated to: {gender_value}')
        if wx_fields:
            wx_user.save(update_fields=wx_fields)
            logger.info(f'WxUser saved with fields: {wx_fields}')

    try:
        customer = user.customer
        customer_fields = []
        if nickname and customer.nickname != nickname:
            customer.nickname = nickname
            customer_fields.append('nickname')
        if avatar and str(customer.avatar) != avatar:
            customer.avatar = avatar
            customer_fields.append('avatar')
        if phone and customer.phone != phone:
            customer.phone = phone
            customer_fields.append('phone')
        if gender is not None and customer.gender != gender:
            customer.gender = gender
            customer_fields.append('gender')
            logger.info(f'Customer gender updated to: {gender}')
        if customer_fields:
            customer.save(update_fields=customer_fields)
            logger.info(f'Customer saved with fields: {customer_fields}')
    except Exception as e:
        logger.warning(f'Failed to sync customer: {e}')

    try:
        employee = user.get_active_employee()
        if not employee:
            return wx_user
        employee_fields = []
        if nickname and employee.nickname != nickname:
            employee.nickname = nickname
            employee_fields.append('nickname')
        if phone and employee.phone != phone:
            employee.phone = phone
            employee_fields.append('phone')
        if gender is not None and employee.gender != gender:
            employee.gender = gender
            employee_fields.append('gender')
            logger.info(f'Employee gender updated to: {gender}')
        if avatar:
            avatar_name = str(avatar).strip()
            if str(employee.avatar) != avatar_name:
                employee.avatar = avatar_name
                employee_fields.append('avatar')
        if employee_fields:
            employee.save(update_fields=employee_fields)
            logger.info(f'Employee saved with fields: {employee_fields}')
    except Exception as e:
        logger.warning(f'Failed to sync employee: {e}')

    return wx_user


def parse_member_slots(member):
    """解析成员占用的席位数（每人只占1个席位）"""
    if not member:
        return 0
    return 1


def get_active_order_members(order):
    return OrderMember.objects.filter(
        order=order,
        is_deleted=False,
        status__in=ACTIVE_ORDER_MEMBER_STATUSES,
    )


def get_order_member_count(order):
    return get_active_order_members(order).count()


def get_effective_locked_slots(order):
    """获取有效锁定席位数（基于实际接取人数）"""
    active_slots = sum(parse_member_slots(member) for member in get_active_order_members(order))
    return active_slots


def get_remaining_slots(order):
    """获取剩余可接取席位数"""
    return max(0, int(order.quantity or 0) - get_effective_locked_slots(order))


def get_active_order_member(order, employee):
    if not employee:
        return None
    return OrderMember.objects.filter(
        order=order,
        is_deleted=False,
        employee=employee,
        status__in=ACTIVE_ORDER_MEMBER_STATUSES,
    ).first()


def sync_order_seat_state(order):
    active_members = list(get_active_order_members(order).select_related('employee').order_by('id'))
    effective_locked_slots = get_effective_locked_slots(order)
    updated_fields = []

    if order.locked_slots != effective_locked_slots:
        order.locked_slots = effective_locked_slots
        updated_fields.append('locked_slots')

    if active_members:
        first_member = active_members[0]
        if order.leader_id != first_member.employee_id:
            order.leader = first_member.employee
            updated_fields.append('leader')
    elif order.leader_id is not None and order.status in ['published', 'confirming']:
        order.leader = None
        updated_fields.append('leader')

    if updated_fields:
        updated_fields.append('updated_at')
        order.save(update_fields=updated_fields)

    return active_members


def ensure_order_leader(order):
    if order.leader_id:
        return order.leader
    first_member = get_active_order_members(order).select_related('employee').order_by('id').first()
    if first_member:
        order.leader = first_member.employee
        order.save(update_fields=['leader', 'updated_at'])
        return first_member.employee
    return None


def build_dasher_order_flags(order, employee):
    member = get_active_order_member(order, employee) if employee else None
    is_member = bool(member)
    is_leader = bool(employee and order.leader_id == employee.id)
    remaining_slots = get_remaining_slots(order)
    is_formally_claimed = order.status in FORMAL_ORDER_STATUSES or remaining_slots <= 0

    return {
        'is_order_member': is_member,
        'is_order_leader': is_leader,
        'can_claim': order.status == 'published' and remaining_slots > 0 and not is_member,
        'can_invite': order.status == 'published' and remaining_slots > 0 and is_leader,
        'can_give_up': is_member and (
            order.status == 'published' or (order.status in ['confirming', 'claimed'] and is_leader)
        ),
        'can_start': order.status == 'claimed' and is_leader,
        'can_transfer': order.status in ['claimed', 'in_progress'] and is_member,
        'can_discount': order.status in ['claimed', 'in_progress'] and is_member,
        'can_manage_order': is_leader or is_member,
        'is_formally_claimed': is_formally_claimed,
    }


def get_wx_openid(code):
    """通过 code 换取 openid"""
    import logging
    logger = logging.getLogger(__name__)

    if not WX_APPID or not WX_SECRET:
        logger.warning('WX_APPID or WX_SECRET is not configured, using mock openid for testing')
        # 开发模式使用固定openid，确保同一设备登录不会创建新账号
        # 生产环境必须配置真实的WX_APPID和WX_SECRET
        mock_openid = 'dev_test_openid_001'
        return {
            'openid': mock_openid,
            'session_key': f'mock_session_{mock_openid}',
        }

    url = 'https://api.weixin.qq.com/sns/jscode2session'
    params = {
        'appid': WX_APPID,
        'secret': WX_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code',
    }
    try:
        resp = requests.get(url, params=params, timeout=10, verify=False)
        data = resp.json()
        logger.info(f'WeChat login response: {data}')
        if 'openid' in data:
            return data
        if 'errcode' in data:
            logger.error(f'WeChat login error: errcode={data.get("errcode")}, errmsg={data.get("errmsg")}')
        return None
    except Exception as e:
        logger.error(f'WeChat login exception: {str(e)}')
        return None


@api_view(['POST'])
@permission_classes([AllowAny])
def wx_login(request):
    """微信小程序登录"""
    code = request.data.get('code')
    if not code:
        return error_response(msg='缺少code参数')

    # 换取 openid
    wx_data = get_wx_openid(code)
    if not wx_data:
        return error_response(msg='微信登录失败，请重试')

    openid = wx_data['openid']
    session_key = wx_data.get('session_key', '')

    # 获取或创建微信用户
    wx_user, created = WxUser.objects.get_or_create(
        openid=openid,
        defaults={'session_key': session_key}
    )
    if not created:
        wx_user.session_key = session_key
        wx_user.last_login = timezone.now()
        wx_user.save(update_fields=['session_key', 'last_login'])

    # 获取或创建系统用户
    if not wx_user.user:
        username = f'wx_{openid[-8:]}'
        # 确保用户名唯一
        counter = 0
        base_username = username
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f'{base_username}_{counter}'

        user = User.objects.create_user(
            username=username,
            nickname=f'用户{openid[-6:]}',
        )
        wx_user.user = user
        wx_user.save(update_fields=['user'])
    else:
        user = wx_user.user

    user.ensure_display_id()

    # 封禁拦截：封禁中的用户不允许登录，明确返回封禁原因与截止时间
    if user.is_banned_active():
        from apps.account.ban_utils import ban_info
        info = ban_info(user)
        return error_response(
            msg='账号已被封禁，无法登录',
            code=4010,
            data={
                'banned': True,
                'permanent': info.get('permanent', False),
                'ban_until': info.get('ban_until'),
                'ban_until_display': info.get('ban_until_display'),
                'ban_reason': info.get('ban_reason', ''),
            },
        )

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    # 判断用户类型
    is_dasher = bool(user.get_active_employee())

    # 只有非打手用户才自动创建客户记录
    from apps.customer.models import Customer
    customer = None
    if not is_dasher:
        customer, created = Customer.objects.get_or_create(
            user=user,
            defaults={
                'nickname': wx_user.nickname or user.nickname or f'用户{openid[-6:]}',
                'avatar': wx_user.avatar or '',
                'phone': wx_user.phone or '',
                'source': '小程序',
            }
        )
        if not created:
            if wx_user.nickname and customer.nickname != wx_user.nickname:
                customer.nickname = wx_user.nickname
            if wx_user.avatar and customer.avatar != wx_user.avatar:
                customer.avatar = wx_user.avatar
            if wx_user.phone and customer.phone != wx_user.phone:
                customer.phone = wx_user.phone
            customer.save()
    else:
        # 打手登录时，删除可能存在的 Customer 记录
        Customer.objects.filter(user=user, is_deleted=False).update(is_deleted=True)

    related = get_related_profile_objects(user)
    display_nickname = choose_display_nickname(
        user,
        wx_user=wx_user,
        customer=customer,
        employee=related['employee'],
        fallback=f'用户{openid[-6:]}',
    )
    wx_user = sync_profile_tables(
        user,
        nickname=display_nickname,
        avatar=wx_user.avatar or field_file_url(user.avatar) or field_file_url(customer.avatar if customer else ''),
        phone=wx_user.phone or user.phone or (customer.phone if customer else ''),
    )

    # 生成 JWT token
    refresh = RefreshToken.for_user(user)
    token = str(refresh.access_token)

    # 判断用户身份
    user_type = 'customer'
    try:
        if user.get_active_employee():
            user_type = 'dasher'
    except Exception:
        pass

    return success_response({
        'token': token,
        'refresh': str(refresh),
        'user_info': {
            'id': user.id,
            'nickname': display_nickname,
            'avatar': wx_user.avatar or field_file_url(user.avatar) or field_file_url(customer.avatar if customer else ''),
            'phone': wx_user.phone or user.phone or (customer.phone if customer else '') or '',
            'gender': user.gender or 'unknown',
            'user_type': user_type,
            'customer_id': customer.id if customer else None,
            'display_id': user.display_id or '',
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def test_login(request):
    """测试登录（开发环境使用）"""
    user_type = request.data.get('user_type', 'customer')

    if user_type == 'dasher':
        # 登录打手账号
        try:
            employee = Employee.objects.select_related('user').filter(is_deleted=False).first()
            if not employee:
                return error_response(msg='没有打手账号，请先在后台创建')
            user = employee.user
        except Exception:
            return error_response(msg='打手账号不存在')
    elif user_type == 'cs':
        # 登录客服账号
        try:
            from apps.customer.models import CustomerService
            cs = CustomerService.objects.select_related('customer__user').filter(is_deleted=False).exclude(
                customer__user__employee__is_deleted=False
            ).first()
            if not cs:
                return error_response(msg='没有客服账号，请先在后台创建')
            user = cs.customer.user
        except Exception:
            return error_response(msg='客服账号不存在')
    else:
        # 登录客户账号
        try:
            from apps.customer.models import Customer
            customer = Customer.objects.select_related('user').filter(is_deleted=False).exclude(
                user__employee__is_deleted=False
            ).first()
            if not customer:
                return error_response(msg='没有客户账号，请先在后台创建')
            user = customer.user
        except Exception:
            return error_response(msg='客户账号不存在')

    if user.is_banned_active():
        from apps.account.ban_utils import ban_info
        info = ban_info(user)
        return error_response(
            msg='账号已被封禁，无法登录', code=4010,
            data={
                'banned': True,
                'permanent': info.get('permanent', False),
                'ban_until': info.get('ban_until'),
                'ban_until_display': info.get('ban_until_display'),
                'ban_reason': info.get('ban_reason', ''),
            },
        )

    # 生成 JWT token
    refresh = RefreshToken.for_user(user)
    token = str(refresh.access_token)

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    related = get_related_profile_objects(user)
    nickname = choose_display_nickname(
        user,
        wx_user=related['wx_user'],
        customer=related['customer'],
        employee=related['employee'],
        fallback='测试用户',
    )
    avatar = (
        related['wx_user'].avatar if related['wx_user'] else ''
    ) or field_file_url(user.avatar) or field_file_url(related['customer'].avatar if related['customer'] else '') or field_file_url(related['employee'].avatar if related['employee'] else '')
    phone = (
        related['wx_user'].phone if related['wx_user'] else ''
    ) or user.phone or (related['customer'].phone if related['customer'] else '') or (related['employee'].phone if related['employee'] else '')

    customer_id = None
    if related['customer']:
        customer_id = related['customer'].id

    return success_response({
        'token': token,
        'refresh': str(refresh),
        'user_info': {
            'id': user.id,
            'nickname': nickname,
            'avatar': avatar,
            'phone': phone,
            'user_type': user_type,
            'customer_id': customer_id,
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wx_update_user(request):
    """更新微信用户信息"""
    user = request.user
    nickname = request.data.get('nickname')
    avatar = request.data.get('avatar')
    gender = request.data.get('gender')

    sync_profile_tables(
        user,
        nickname=nickname,
        avatar=avatar,
        gender={'1': 'male', '2': 'female', '0': 'unknown'}.get(str(gender)) if gender is not None else None,
    )

    return success_response(msg='更新成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wx_bind_phone(request):
    """绑定手机号（需要微信手机号快速验证）"""
    user = request.user
    phone = request.data.get('phone')
    if not phone:
        return error_response(msg='缺少手机号')

    try:
        wx_user = user.wx_user
        wx_user.phone = phone
        wx_user.save(update_fields=['phone'])
    except WxUser.DoesNotExist:
        pass

    user.phone = phone
    user.save(update_fields=['phone'])

    return success_response(msg='绑定成功')


# ============ 首页数据 ============


@api_view(['GET'])
@permission_classes([AllowAny])
def home_data(request):
    """首页聚合数据"""
    banners = Banner.objects.filter(status=True, is_deleted=False)[:5]
    announcements = Announcement.objects.filter(status=True, is_deleted=False)[:3]
    games = GameCategory.objects.filter(status=True, is_deleted=False).order_by('sort', 'id')

    # 推荐陪玩师（在线且评分高）
    employees = Employee.objects.filter(
        status__in=['idle', 'busy'],
        is_deleted=False
    ).select_related('user', 'user__wx_user').prefetch_related('skills', 'tags').order_by('-rating', 'sort')[:8]

    employee_list = []
    for emp in employees:
        skills = []
        for rel in emp.skill_relations.filter(
            skill__status=True, is_deleted=False
        ).select_related('skill').order_by('-is_enabled', 'skill__sort', 'id')[:3]:
            skills.append({
                'name': rel.skill.name,
                'price': float(rel.unit_price),
                'is_enabled': rel.is_enabled,
                'pricing_unit': rel.skill.pricing_unit,
            })
        # 获取评价数量
        review_count = OrderComment.objects.filter(employee=emp, is_deleted=False).count()

        employee_list.append({
            'id': emp.id,
            'display_id': emp.user.display_id or '',
            'nickname': emp.nickname or emp.real_name,
            'avatar': employee_avatar_url(emp),
            'gender': emp.gender,
            'level': emp.level,
            'level_num': emp.level_num,
            'assessment_mode': emp.assessment_mode,
            'assessment_mode_display': emp.get_assessment_mode_display(),
            'rating': float(emp.rating),
            'review_count': review_count,
            'order_count': emp.order_count,
            'intro': emp.intro[:50] if emp.intro else '',
            'skills': skills,
            'is_online': emp.online_status,
        })

    # 明星打手（TOP3，按star_sort排序）
    star_list = []
    try:
        star_dashers = Employee.objects.filter(
            is_star=True, is_deleted=False
        ).order_by('star_sort', 'id')[:3]
        for emp in star_dashers:
            star_list.append({
                'id': emp.id,
                'nickname': emp.nickname or emp.real_name,
                'avatar': employee_avatar_url(emp),
                'level': emp.level,
                'level_num': emp.level_num,
                'order_count': emp.order_count,
            })
    except Exception:
        pass

    return success_response({
        'banners': BannerSerializer(banners, many=True, context={'request': request}).data,
        'announcements': AnnouncementSerializer(announcements, many=True, context={'request': request}).data,
        'games': GameCategorySerializer(games, many=True, context={'request': request}).data,
        'employees': employee_list,
        'star_dashers': star_list,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def game_list(request):
    """游戏分类列表（与首页共用）"""
    games = GameCategory.objects.filter(status=True, is_deleted=False).order_by('sort', 'id')
    return success_response(GameCategorySerializer(games, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recharge_offers(request):
    """充值优惠套餐"""
    return success_response({'list': get_recharge_offers(active_only=True)})


@api_view(['GET'])
@permission_classes([AllowAny])
def agreements(request, slug=None):
    """小程序协议列表/详情，登录前也允许访问。"""
    if slug:
        agreement = get_agreement(slug)
        if not agreement:
            return error_response(msg='协议不存在或已停用', code=404)
        return success_response(agreement)
    items = get_agreements(active_only=True)
    return success_response({
        'list': [
            {
                'key': item['key'],
                'title': item['title'],
                'summary': item.get('summary', ''),
                'sort': item.get('sort', 0),
            }
            for item in items
        ]
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def ranking_list(request):
    """周星榜单 — 明星打手 + 全部排名"""
    # 明星打手 TOP3
    star_list = []
    try:
        star_dashers = Employee.objects.filter(
            is_star=True, is_deleted=False
        ).order_by('star_sort', 'id')[:3]
        for emp in star_dashers:
            star_list.append({
                'id': emp.id,
                'nickname': emp.nickname or emp.real_name,
                'avatar': employee_avatar_url(emp),
                'level': emp.level,
                'level_num': emp.level_num,
                'order_count': emp.order_count,
            })
    except Exception:
        pass

    # 全部打手排名（按接单数）
    all_ranked = Employee.objects.filter(
        is_deleted=False, order_count__gt=0
    ).order_by('-order_count', 'id')[:50]
    rank_list = []
    for idx, emp in enumerate(all_ranked):
        rank_list.append({
            'rank': idx + 1,
            'id': emp.id,
            'nickname': emp.nickname or emp.real_name,
            'avatar': employee_avatar_url(emp),
            'level': emp.level,
            'level_num': emp.level_num,
            'order_count': emp.order_count,
            'is_star': emp.is_star,
        })

    return success_response({
        'stars': star_list,
        'ranking': rank_list,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def game_banners(request, game_id):
    """获取指定游戏的轮播图"""
    banners = GameBanner.objects.filter(
        game_id=game_id, status=True, is_deleted=False
    ).order_by('sort', 'id')[:5]
    return success_response(GameBannerSerializer(banners, many=True, context={'request': request}).data)


# ============ 陪玩师模块 ============


def _rank_payload(game_name='', rank_name='', game_id=0, rank_id=0):
    game_name = fix_mojibake(game_name or '')
    rank_name = fix_mojibake(rank_name or '')
    return {
        'game_id': game_id or 0,
        'game_name': game_name,
        'rank_id': rank_id or 0,
        'rank_name': rank_name,
        'badge': f'{game_name}-{rank_name}' if game_name and rank_name else '',
    }


def _employee_game_rank_payload(employee, game_id):
    if not game_id:
        return _rank_payload()
    try:
        rel = EmployeeGameRank.objects.select_related('game_category', 'rank').get(
            employee=employee,
            game_category_id=game_id,
            is_deleted=False,
            rank__status=True,
            rank__is_deleted=False,
        )
    except EmployeeGameRank.DoesNotExist:
        return _rank_payload()
    return _rank_payload(
        game_name=rel.game_category.name if rel.game_category else '',
        rank_name=rel.rank.name if rel.rank else '',
        game_id=rel.game_category_id,
        rank_id=rel.rank_id,
    )

@api_view(['GET'])
@permission_classes([AllowAny])
def employee_list(request):
    """陪玩师列表"""
    skill_id = request.GET.get('skill_id')
    game_id = request.GET.get('game_id')
    level = request.GET.get('level')
    gender = request.GET.get('gender')
    keyword = request.GET.get('keyword', '').strip()
    sort_by = request.GET.get('sort', 'rating')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    queryset = Employee.objects.filter(
        status__in=['idle', 'busy'],
        is_deleted=False
    ).select_related('user', 'user__wx_user').prefetch_related('skills', 'tags', 'game_categories')

    if skill_id:
        queryset = queryset.filter(
            skill_relations__skill_id=skill_id,
            skill_relations__is_enabled=True,
            skill_relations__is_deleted=False,
        )
    if game_id:
        # 只显示直接绑定了该游戏分类的打手
        queryset = queryset.filter(game_categories__id=game_id).distinct()
    if level:
        queryset = queryset.filter(level=level)
    if gender:
        queryset = queryset.filter(gender=gender)
    if keyword:
        queryset = queryset.filter(
            Q(nickname__icontains=keyword) |
            Q(real_name__icontains=keyword) |
            Q(intro__icontains=keyword)
        )

    base_queryset = queryset

    # 排序
    sort_map = {
        'rating': '-rating',
        'hot': '-order_count',
        'order_count': '-order_count',
        'price': 'skill_relations__unit_price',
        'new': '-created_at',
    }
    is_star_filter = sort_by == 'star'
    if is_star_filter:
        # 明星打手筛选：只看 is_star，按 star_sort 排序
        queryset = queryset.filter(is_star=True)
        order_field = 'star_sort'
    else:
        order_field = sort_map.get(sort_by, '-rating')
    queryset = queryset.order_by(order_field).distinct()

    total = queryset.count()
    # 当前筛选条件下明星打手总数（供前端判断是否显示"明星"筛选入口）
    star_total = base_queryset.filter(is_star=True).distinct().count()
    start = (page - 1) * page_size
    employees = queryset[start:start + page_size]

    employee_list = []
    for emp in employees:
        current_game_rank = _employee_game_rank_payload(emp, game_id)
        skills = []
        for rel in emp.skill_relations.filter(
            skill__status=True, is_deleted=False
        ).select_related('skill', 'skill_level', 'skill__required_rank', 'skill__game_category').order_by(
            '-is_enabled', 'skill__sort', 'id'
        )[:5]:
            skills.append({
                'id': rel.skill.id,
                'name': fix_mojibake(rel.skill.name),
                'price': float(rel.unit_price),
                'level': fix_mojibake(rel.skill_level.name) if rel.skill_level else '',
                'required_rank': fix_mojibake(rel.skill.required_rank.name) if rel.skill.required_rank else '',
                'is_enabled': rel.is_enabled,
                'pricing_unit': rel.skill.pricing_unit,
                'icon': rel.skill.icon or '',
            })
        tags = [{'name': t.name, 'color': t.color} for t in emp.tags.filter(status=True)[:5]]
        game_categories = [
            {'id': gc.id, 'name': gc.name}
            for gc in emp.game_categories.filter(status=True).order_by('sort', 'id')
        ]
        # 获取评价数量
        review_count = OrderComment.objects.filter(employee=emp, is_deleted=False).count()

        employee_list.append({
            'id': emp.id,
            'display_id': emp.user.display_id or '',
            'nickname': fix_mojibake(emp.nickname or emp.real_name),
            'avatar': employee_avatar_url(emp),
            'gender': emp.gender if emp.gender != 'unknown' else (emp.user.gender if emp.user else 'unknown'),
            'age': emp.age,
            'level': emp.level,
            'level_num': emp.level_num,
            'assessment_mode': emp.assessment_mode,
            'assessment_mode_display': emp.get_assessment_mode_display(),
            'rating': float(emp.rating),
            'review_count': review_count,
            'order_count': emp.order_count,
            'fans_count': getattr(emp, 'fans_count', 0),
            'intro': emp.intro[:80] if emp.intro else '',
            'skills': skills,
            'tags': tags,
            'game_categories': game_categories,
            'game_rank': current_game_rank,
            'game_rank_badge': current_game_rank['badge'],
            'is_online': emp.online_status,
            'is_star': emp.is_star,
        })

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'star_total': star_total,
        'list': employee_list,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def employee_detail(request, emp_id):
    """陪玩师详情"""
    try:
        emp = Employee.objects.select_related('user', 'user__wx_user').get(id=emp_id, is_deleted=False)
    except Employee.DoesNotExist:
        return error_response(msg='陪玩师不存在')

    rank_map = {}
    for rank_rel in emp.game_rank_relations.filter(
        is_deleted=False, rank__status=True, rank__is_deleted=False
    ).select_related('game_category', 'rank'):
        rank_map[rank_rel.game_category_id] = _rank_payload(
            game_name=rank_rel.game_category.name if rank_rel.game_category else '',
            rank_name=rank_rel.rank.name if rank_rel.rank else '',
            game_id=rank_rel.game_category_id,
            rank_id=rank_rel.rank_id,
        )
    game_rank_list = sorted(rank_map.values(), key=lambda item: (item.get('game_name') or '', item.get('rank_name') or ''))

    skills = []
    for rel in emp.skill_relations.filter(
        skill__status=True, is_deleted=False
    ).select_related('skill', 'skill_level', 'skill__required_rank', 'skill__game_category').order_by(
        '-is_enabled', 'skill__sort', 'id'
    ):
        game_category_id = rel.skill.game_category_id or 0
        game_name = rel.skill.game_category.name if rel.skill.game_category else ''
        game_rank = rank_map.get(game_category_id) or _rank_payload(game_name=game_name, game_id=game_category_id)
        skills.append({
            'id': rel.skill.id,
            'name': fix_mojibake(rel.skill.name),
            'category': fix_mojibake(rel.skill.category),
            'game_id': game_category_id,
            'game_name': fix_mojibake(game_name),
            'price': float(rel.unit_price),
            'level': fix_mojibake(rel.skill_level.name) if rel.skill_level else '',
            'required_rank': fix_mojibake(rel.skill.required_rank.name) if rel.skill.required_rank else '',
            'game_rank': game_rank,
            'game_rank_badge': game_rank['badge'],
            'min_people': rel.skill.min_people or 1,
            'icon': rel.skill.icon or '',
            'is_enabled': rel.is_enabled,
            'pricing_unit': rel.skill.pricing_unit,
            'assignment_source': rel.assignment_source,
        })

    tags = [{'name': t.name, 'color': t.color} for t in emp.tags.filter(status=True)]
    game_categories = [
        {'id': gc.id, 'name': gc.name, 'icon': gc.icon or ''}
        for gc in emp.game_categories.filter(status=True).order_by('sort', 'id')
    ]

    # 最近评价
    comments = OrderComment.objects.filter(
        employee=emp, is_deleted=False
    ).select_related('customer').order_by('-created_at')[:5]
    comment_list = []
    for c in comments:
        # 将逗号分隔的标签字符串转换为数组
        tags_list = [t.strip() for t in c.tags.split(',') if t.strip()] if c.tags else []
        # 将逗号分隔的图片URL字符串转换为数组
        images_list = [img.strip() for img in c.images.split(',') if img.strip()] if c.images else []
        comment_list.append({
            'id': c.id,
            'rating': c.rating,
            'content': c.content,
            'tags': tags_list,
            'images': images_list,
            'customer_name': c.customer.nickname if not c.is_anonymous else '匿名用户',
            'customer_avatar': field_file_url(c.customer.avatar),
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    # 可用价格（根据员工拥有的技能）
    skill_ids = emp.skill_relations.filter(skill__status=True).values_list('skill_id', flat=True)
    prices = OrderPrice.objects.filter(
        skill_id__in=skill_ids, status=True
    ).select_related('skill')

    return success_response({
        'id': emp.id,
        'display_id': emp.user.display_id or '',
        'nickname': fix_mojibake(emp.nickname or emp.real_name),
        'real_name': fix_mojibake(emp.real_name),
        'avatar': employee_avatar_url(emp),
        'gender': emp.gender,
        'age': emp.age,
        'level': emp.level,
        'level_num': emp.level_num,
        'rating': float(emp.rating),
        'order_count': emp.order_count,
        'total_duration': emp.total_duration,
        'fans_count': getattr(emp, 'fans_count', 0),
        'intro': emp.intro or '',
        'voice_intro': build_media_url(emp.voice_intro, request) if emp.voice_intro else '',
        'voice_intro_url': build_media_url(emp.voice_intro, request) if emp.voice_intro else '',
        'voice_duration': emp.voice_duration or 0,
        'skills': skills,
        'tags': tags,
        'game_ranks': game_rank_list,
        'game_rank_badge': game_rank_list[0]['badge'] if game_rank_list else '',
        'game_categories': game_categories,
        'comments': comment_list,
        'photos': emp.photos or [],
        'is_online': emp.online_status,
    })


# ============ 订单模块 ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """创建订单"""
    user = request.user
    try:
        wx_user = user.wx_user
    except WxUser.DoesNotExist:
        return error_response(msg='用户未登录小程序')

    try:
        customer = user.customer
    except Exception:
        from apps.customer.models import Customer
        customer = Customer.objects.create(
            user=user,
            nickname=user.nickname or f'用户{user.id}',
        )

    skill_id = request.data.get('skill_id')
    employee_id = request.data.get('employee_id')
    if employee_id:
        employee_id = int(employee_id)
    duration = request.data.get('duration', 60)
    purchase_quantity_raw = request.data.get('purchase_quantity')
    quantity = request.data.get('quantity', 1)
    game_id = request.data.get('game_id', '')
    game_name = request.data.get('game_name', '')
    server = request.data.get('server', '')
    remark = request.data.get('remark', '')

    if not skill_id:
        return error_response(msg='请选择服务类型')

    try:
        skill = EmployeeSkill.objects.get(id=skill_id, status=True)
    except EmployeeSkill.DoesNotExist:
        return error_response(msg='服务类型不存在')

    # 校验数量
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        return error_response(msg='购买数量不能小于1')

    try:
        purchase_quantity = Decimal(str(
            purchase_quantity_raw if purchase_quantity_raw is not None
            else (Decimal(str(duration)) / Decimal('60') if skill.pricing_unit == 'hour' else 1)
        ))
    except (InvalidOperation, TypeError, ValueError):
        return error_response(msg='购买数量格式不正确')
    if purchase_quantity <= 0:
        return error_response(msg='购买数量必须大于0')
    if skill.pricing_unit == 'round' and purchase_quantity % 1 != 0:
        return error_response(msg='按局计价时局数必须为整数')

    # 计算价格
    unit_price = 0
    if employee_id:
        try:
            relation = EmployeeSkillRelation.objects.get(
                employee_id=employee_id, skill_id=skill_id,
                is_deleted=False, is_enabled=True
            )
            unit_price = float(relation.unit_price)
        except EmployeeSkillRelation.DoesNotExist:
            return error_response(msg='该打手暂未开启此技能')

    if unit_price == 0:
        price_obj = OrderPrice.objects.filter(skill_id=skill_id, status=True).first()
        if price_obj:
            unit_price = float(price_obj.unit_price)

    total_amount = Decimal(str(unit_price)) * purchase_quantity * quantity if unit_price else Decimal('0')

    # 生成订单号（包含随机数避免重复）
    import random
    random_suffix = random.randint(1000, 9999)
    order_no = f'WX{timezone.now().strftime("%Y%m%d%H%M%S")}{str(user.id).zfill(4)}{random_suffix}'

    order = Order.objects.create(
        order_no=order_no,
        customer=customer,
        skill=skill,
        status=OrderStatus.PUBLISHED,
        duration=duration,
        quantity=quantity,
        purchase_quantity=purchase_quantity,
        settlement_unit=skill.pricing_unit,
        unit_price=unit_price,
        total_amount=round(total_amount, 2),
        pay_amount=round(total_amount, 2),
        game_id=game_id,
        game_name=game_name,
        server=server,
        remark=remark,
        platform='mini_program',
        assigned_employee_id=employee_id if employee_id else None,
    )

    return success_response({
        'order_id': order.id,
        'order_no': order.order_no,
        'total_amount': float(order.total_amount),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_self_service_order_legacy(request):
    """客户自助下单（支持多技能项）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        from apps.customer.models import Customer
        customer = Customer.objects.create(
            user=user,
            nickname=user.nickname or f'用户{user.id}',
        )

    game_name = request.data.get('game_name', '')
    game_id = request.data.get('game_id', '')
    content = request.data.get('content', '')
    quantity = request.data.get('quantity', 1)
    items = request.data.get('items', [])

    if not items:
        return error_response(msg='请至少选择一个技能')

    # 校验人数
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        quantity = 1

    # 计算总价和总时长
    total_amount = 0
    total_duration = 0
    order_items = []

    for item in items:
        skill_id = item.get('skill_id')
        skill_name = item.get('skill_name', '')
        duration = item.get('duration', 60)
        unit_price = item.get('unit_price', 0)

        if not skill_id:
            continue

        item_amount = float(unit_price) * duration / 60
        total_amount += item_amount
        total_duration += duration

        order_items.append({
            'skill_id': skill_id,
            'skill_name': skill_name,
            'duration': duration,
            'unit_price': float(unit_price),
            'amount': item_amount,
        })

    if not order_items:
        return error_response(msg='请至少选择一个有效的技能')

    total_amount = total_amount * quantity

    # 自动生成标题：游戏名 + 技能数
    auto_title = f'{game_name}自助下单' if game_name else '自助下单'

    # 生成订单号
    import random
    random_suffix = random.randint(1000, 9999)
    order_no = f'SV{timezone.now().strftime("%Y%m%d%H%M%S")}{str(user.id).zfill(4)}{random_suffix}'

    order = Order.objects.create(
        order_no=order_no,
        customer=customer,
        status=OrderStatus.PUBLISHED,
        title=auto_title,
        order_type='self_service',
        duration=total_duration,
        quantity=quantity,
        unit_price=total_amount / total_duration * 60 if total_duration else 0,
        total_amount=total_amount,
        pay_amount=total_amount,
        game_id=game_id,
        game_name=game_name,
        remark=content,
        platform='mini_program',
    )

    # 为每个技能项创建订单成员记录
    for item in order_items:
        skill_obj = None
        try:
            skill_obj = EmployeeSkill.objects.get(id=item['skill_id'])
        except Exception:
            pass

        OrderMember.objects.create(
            order=order,
            skill=skill_obj,
            unit_price=item['unit_price'],
            duration=item['duration'],
            amount=item['amount'] * quantity,
            status='assigned',
            remark=item['skill_name'],
        )

    return success_response({
        'order_id': order.id,
        'order_no': order.order_no,
        'total_amount': float(order.total_amount),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_self_service_order(request):
    """Create an order from a server-owned sellable specification."""
    user = request.user
    from apps.customer.models import Customer
    try:
        # 余额校验与扣款必须锁定同一客户行，防止并发下单重复通过余额校验。
        customer = Customer.objects.select_for_update().get(user=user)
    except Customer.DoesNotExist:
        customer = Customer.objects.create(
            user=user, nickname=user.nickname or f'用户{user.id}'
        )

    checkout_preorder, preorder_error = _lock_checkout_preorder(request)
    if preorder_error:
        return preorder_error

    gameplay = SkillGameplay.objects.select_for_update().select_related(
        'skill', 'skill__game_category'
    ).filter(
        id=request.data.get('gameplay_id'), status=True,
        skill__status=True, skill__self_service_enabled=True,
    ).first()
    if gameplay is None:
        return error_response(msg='该玩法不存在或已下架')

    skill = gameplay.skill
    assigned_employee = None
    assigned_employee_id = request.data.get('assigned_employee_id')
    if assigned_employee_id:
        assigned_employee = Employee.objects.filter(
            id=assigned_employee_id,
            status__in=['idle', 'busy'],
            is_deleted=False,
            skill_relations__skill=skill,
            skill_relations__is_enabled=True,
            skill_relations__is_deleted=False,
        ).distinct().first()
        if assigned_employee is None:
            return error_response(msg='指定的打手当前无法接取该服务')

    game_account = None
    game_account_id = request.data.get('game_account_id')
    if game_account_id:
        game_account = GameAccount.objects.filter(
            id=game_account_id, user=user, is_deleted=False,
        ).select_related('game_category').first()
        if game_account is None:
            return error_response(msg='请选择有效的游戏账号')
        if skill.game_category_id and game_account.game_category_id != skill.game_category_id:
            return error_response(msg='所选游戏账号与当前游戏不匹配')

    choice_snapshot = {
        'game_account_id': game_account.id if game_account else None,
        'game_account_name': game_account.game_account if game_account else '',
        'game_account_category': game_account.game_category.name if game_account else '',
        'assigned_employee_id': assigned_employee.id if assigned_employee else None,
        'assigned_employee_name': (
            assigned_employee.nickname or assigned_employee.real_name
        ) if assigned_employee else '',
    }
    if gameplay.order_mode == 'preset':
        preset_item = GameplayPresetItem.objects.select_for_update().filter(
            id=request.data.get('preset_item_id'), gameplay=gameplay,
            status=True, is_deleted=False,
        ).first()
        if preset_item is None:
            return error_response(msg='请选择有效的预制单项目')
        if not preset_item.display_image or not preset_item.content:
            return error_response(msg='该预制单配置不完整，请联系管理员')
        # 数量锁定为预制单所需人数（最低1），打手由系统/在线打手自由接单匹配
        preset_quantity = preset_item.required_people or 1
        preset_price = Decimal(preset_item.price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if preset_price < 0:
            return error_response(msg='该预制单价格配置无效，请联系管理员')
        unit_coin_cost = int(
            (preset_price * Decimal('10')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        )
        coin_cost = unit_coin_cost * preset_quantity
        total_price = (preset_price * preset_quantity).quantize(Decimal('0.01'))
        charged_amount = (Decimal(coin_cost) / Decimal('10')).quantize(Decimal('0.01'))
        if customer.coins_frozen:
            return error_response(msg='黑钻已被冻结，无法下单', code=403)
        if coin_cost > 0 and (customer.coins or 0) < coin_cost:
            return error_response(msg=f'黑钻不足，需要{coin_cost}黑钻，当前仅有{customer.coins or 0}黑钻')
        import random
        order_no = (
            f'SV{timezone.now().strftime("%Y%m%d%H%M%S")}'
            f'{str(user.id).zfill(4)}{random.randint(1000, 9999)}'
        )
        game_name = skill.game_category.name if skill.game_category else skill.name
        snapshot = {
            'version': 4,
            'order_mode': 'preset',
            'skill_id': skill.id,
            'skill_name': skill.name,
            'gameplay_id': gameplay.id,
            'gameplay_name': gameplay.name,
            'preset_item_id': preset_item.id,
            'preset_item_name': preset_item.name,
            'display_image': build_media_url(preset_item.display_image, request),
            'preset_content': preset_item.content,
            'preset_remark': preset_item.remark,
            'quantity': preset_quantity,
            'required_people': preset_quantity,
            'unit_price': float(preset_price),
            'unit_coins': unit_coin_cost,
            'total_amount': float(total_price),
            'pay_amount': float(charged_amount),
            'total_coins': coin_cost,
            **choice_snapshot,
        }
        order = Order.objects.create(
            order_no=order_no,
            customer=customer,
            skill=skill,
            status=OrderStatus.PUBLISHED,
            title=f'{skill.name} · {gameplay.name} · {preset_item.name}',
            order_type='self_service',
            duration=0,
            quantity=1,
            purchase_quantity=preset_quantity,
            settlement_unit='item',
            self_service_snapshot=snapshot,
            unit_price=preset_price,
            total_amount=total_price,
            pay_amount=charged_amount,
            game_id=str(skill.game_category_id or ''),
            game_name=game_name,
            remark=preset_item.remark or preset_item.content,
            platform='mini_program',
            assigned_employee=assigned_employee,
        )
        OrderMember.objects.create(
            order=order,
            skill=skill,
            unit_price=preset_price,
            duration=0,
            amount=charged_amount,
            status='assigned',
            remark=(preset_item.content or preset_item.name)[:500],
        )
        customer.coins = (customer.coins or 0) - coin_cost
        customer.total_amount = (customer.total_amount or Decimal('0')) + charged_amount
        customer.total_orders = (customer.total_orders or 0) + 1
        customer.last_order_date = timezone.now()
        if not customer.first_order_date:
            customer.first_order_date = timezone.now()
        customer.save(update_fields=[
            'coins', 'total_amount', 'total_orders', 'last_order_date', 'first_order_date'
        ])
        if coin_cost > 0:
            from apps.customer.models import CustomerConsumeRecord
            CustomerConsumeRecord.objects.create(
                customer=customer,
                order_no=order_no,
                amount=charged_amount,
                type='order',
                remark=f'预制单 {skill.name}·{gameplay.name}·{preset_item.name}',
            )
            wallet, _ = Wallet.objects.get_or_create(user=user, type='user')
            wallet.balance = (wallet.balance or Decimal('0')) - charged_amount
            wallet.total_expense = (wallet.total_expense or Decimal('0')) + charged_amount
            wallet.save(update_fields=['balance', 'total_expense'])
            Transaction.objects.create(
                wallet=wallet,
                order_no=order_no,
                transaction_no=f'TXN{timezone.now().strftime("%Y%m%d%H%M%S")}{user.id:04d}{order.id:04d}',
                type='expense',
                category='self_service_order',
                amount=charged_amount,
                balance_after=wallet.balance,
                remark=f'预制单扣减 {coin_cost}黑钻',
                operator=request.user,
            )
        _mark_preorder_used(checkout_preorder)
        return success_response({
            'order_id': order.id,
            'order_no': order.order_no,
            'total_amount': float(total_price),
            'pay_amount': float(charged_amount),
            'total_coins': coin_cost,
            'snapshot': snapshot,
        })

    difficulty = None
    if gameplay.difficulty_enabled:
        difficulty = GameplayDifficulty.objects.filter(
            id=request.data.get('difficulty_id'), gameplay=gameplay, status=True
        ).first()
        if difficulty is None:
            return error_response(msg='请选择有效的难度')

    level = GameplayLevelOption.objects.filter(
        id=request.data.get('level_id'), gameplay=gameplay, status=True
    ).first()
    service = GameplayService.objects.filter(
        id=request.data.get('service_id'), gameplay=gameplay, status=True
    ).first()
    if level is None:
        return error_response(msg='请选择有效的等级')
    if service is None:
        return error_response(msg='请选择有效的服务')

    # 校验：所选服务是否属于该等级允许的列表
    allowed_services = list(getattr(level, 'allowed_services', None) or [])
    if allowed_services and service.name not in allowed_services:
        return error_response(msg=f'等级“{level.name}”不提供服务“{service.name}”')

    # 处理性别选择
    gender_requirement = None
    if gameplay.gender_limit in ('male_only', 'male'):
        gender_requirement = 'male'
    elif gameplay.gender_limit in ('female_only', 'female'):
        gender_requirement = 'female'
    elif gameplay.gender_limit in ('optional', 'unlimited'):
        gender_requirement = request.data.get('gender_requirement', 'any')
        if gender_requirement not in ('any', 'male', 'female'):
            gender_requirement = 'any'
    else:
        gender_requirement = 'any'

    companion_type = request.data.get('companion_type', 'single')
    allowed_companions = {
        'single': {'single'}, 'double': {'double'}, 'both': {'single', 'double'}
    }[gameplay.companion_mode]
    if companion_type not in allowed_companions:
        return error_response(msg='该玩法不支持所选陪玩类型')

    try:
        purchase_quantity = Decimal(str(request.data.get('quantity', gameplay.min_quantity)))
    except (InvalidOperation, TypeError, ValueError):
        return error_response(msg='请输入有效的购买数量')
    if not purchase_quantity.is_finite() or gameplay.quantity_step <= 0:
        return error_response(msg='请输入有效的购买数量')
    if purchase_quantity < gameplay.min_quantity:
        return error_response(msg=f'最低购买数量为{gameplay.min_quantity}')
    if (purchase_quantity - gameplay.min_quantity) % gameplay.quantity_step != 0:
        return error_response(msg=f'购买数量必须按{gameplay.quantity_step}递增')
    if gameplay.settlement_unit == 'hour' and purchase_quantity < Decimal('0.5'):
        return error_response(msg='按小时结算最低为0.5小时')
    if gameplay.settlement_unit == 'round' and purchase_quantity % 1 != 0:
        return error_response(msg='按局结算必须填写整数局数')

    remark = str(request.data.get('remark', request.data.get('content', ''))).strip()
    if gameplay.remark_required and not remark:
        return error_response(msg='该玩法必须填写备注')
    if len(remark) > 500:
        return error_response(msg='备注不能超过500个字')

    trial_requested = bool(request.data.get('trial_requested', False))
    if skill.trial_mode == 'required' and not trial_requested:
        return error_response(msg='该技能下单前必须选择试音')
    if skill.trial_mode == 'disabled':
        trial_requested = False

    def parse_selected_ids(field_name):
        raw_ids = request.data.get(field_name) or []
        if isinstance(raw_ids, str):
            try:
                import json as _json
                raw_ids = _json.loads(raw_ids)
            except Exception:
                raw_ids = []
        if not isinstance(raw_ids, (list, tuple)):
            return []
        return list(dict.fromkeys(int(value) for value in raw_ids if str(value).isdigit()))

    # 玩法附加项目、附加项目下的附加增值、服务类型增值均为可选项。
    addon_ids = parse_selected_ids('addon_ids')
    addon_value_ids = parse_selected_ids('addon_value_ids')
    service_value_ids = parse_selected_ids('service_value_ids')
    if len(addon_ids) > 1:
        return error_response(msg='附加项目只能选择一个')
    if len(addon_value_ids) > 1:
        return error_response(msg='附加增值只能选择一个')
    selected_addons = []
    selected_addon_values = []
    selected_service_values = []
    extra_price_delta = Decimal('0')

    addon_qs = ValueAddedService.objects.filter(
        gameplay=gameplay, status=True, is_deleted=False, id__in=addon_ids
    ).order_by('sort', 'id')
    valid_addon_ids = []
    for addon in addon_qs:
        valid_addon_ids.append(addon.id)
        selected_addons.append({
            'id': addon.id,
            'name': addon.name,
            'description': addon.description or '',
            'price': float(addon.price),
        })
        extra_price_delta += Decimal(str(addon.price))

    if addon_value_ids:
        addon_value_qs = AddonValueAddedService.objects.filter(
            addon_id__in=valid_addon_ids, status=True, is_deleted=False,
            id__in=addon_value_ids,
        ).select_related('addon').order_by('sort', 'id')
        for value in addon_value_qs:
            selected_addon_values.append({
                'id': value.id,
                'addon_id': value.addon_id,
                'addon_name': value.addon.name,
                'name': value.name,
                'description': value.description or '',
                'price': float(value.price),
            })
            extra_price_delta += Decimal(str(value.price))

    if service_value_ids:
        service_value_qs = ServiceValueAdded.objects.filter(
            service=service, status=True, is_deleted=False,
            id__in=service_value_ids,
        ).order_by('sort', 'id')
        for value in service_value_qs:
            selected_service_values.append({
                'id': value.id,
                'service_id': value.service_id,
                'service_name': service.name,
                'name': value.name,
                'description': value.description or '',
                'price': float(value.price),
            })
            extra_price_delta += Decimal(str(value.price))

    addon_ids = valid_addon_ids
    addon_value_ids = [value['id'] for value in selected_addon_values]
    service_value_ids = [value['id'] for value in selected_service_values]

    selected_names = {
        'difficulty_name': difficulty.name if difficulty else '',
        'level_name': level.name,
        'service_name': service.name,
    }

    # 计算性别加价（仅 optional 模式下的具体选择才加价；规则内已覆盖的走 SKU 价）
    gender_price_delta = Decimal('0')
    if gameplay.gender_limit == 'optional':
        if gender_requirement == 'male':
            gender_price_delta = Decimal(gameplay.male_price_delta)
        elif gender_requirement == 'female':
            gender_price_delta = Decimal(gameplay.female_price_delta)

    # 匹配：在 companion_type 范围内，按性别特异度 + 其他字段特异度找最佳
    # 规则 gender_requirement 取值：any(通用) / male(要求男) / female(要求女)
    # 用户选择的 gender_requirement 取值：male / female（optional），any（不限/只男/只女映射后）
    matching_rules = []
    for rule in gameplay.price_rules.filter(status=True, companion_type=companion_type):
        # 性别维度匹配：any 可匹配任何选择；male 只匹配 male；female 只匹配 female
        if rule.gender_requirement == 'any':
            gender_match = True
            gender_score = 0
        elif rule.gender_requirement == 'male':
            gender_match = (gender_requirement == 'male')
            gender_score = 1
        else:  # female
            gender_match = (gender_requirement == 'female')
            gender_score = 1
        if not gender_match:
            continue
        # 其他维度
        field_match = all(
            not getattr(rule, field) or getattr(rule, field) == value
            for field, value in selected_names.items()
        )
        if not field_match:
            continue
        field_score = sum(bool(getattr(rule, field)) for field in selected_names)
        specificity = gender_score + field_score
        matching_rules.append((specificity, rule.id, rule))
    matching_rules.sort(key=lambda item: (item[0], item[1]), reverse=True)

    if matching_rules:
        # SKU 是对应单陪/双陪组合的最终固定单价，不再按双陪二次翻倍。
        matched_rule = matching_rules[0][2]
        unit_price = Decimal(str(matched_rule.unit_price))
        if matched_rule.gender_requirement == 'any':
            unit_price += gender_price_delta
        price_source = 'sku'
    else:
        unit_price = gameplay.base_price + level.price_delta + service.price_delta + gender_price_delta
        if difficulty:
            unit_price += difficulty.price_delta
        if companion_type == 'double':
            unit_price *= 2
        price_source = 'formula'

    # 叠加增值服务单价（直接累加到单位价中，不影响前面的逻辑）
    if extra_price_delta:
        unit_price = Decimal(unit_price) + extra_price_delta

    unit_price = Decimal(unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if unit_price < 0:
        return error_response(msg='该规格价格配置无效')
    total_amount = (unit_price * purchase_quantity).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    coin_cost = int(
        (total_amount * Decimal('10')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    )
    charged_amount = (Decimal(coin_cost) / Decimal('10')).quantize(Decimal('0.01'))
    people_count = 2 if companion_type == 'double' else 1
    duration = int(purchase_quantity * 60) if gameplay.settlement_unit == 'hour' else 0
    game_name = skill.game_category.name if skill.game_category else skill.name

    snapshot = {
        'version': 3,
        'order_mode': 'custom',
        'skill_id': skill.id,
        'skill_name': skill.name,
        'gameplay_id': gameplay.id,
        'gameplay_name': gameplay.name,
        'difficulty_id': difficulty.id if difficulty else None,
        'difficulty': difficulty.name if difficulty else '',
        'level_id': level.id,
        'level': level.name,
        'service_id': service.id,
        'service': service.name,
        'gender_requirement': gender_requirement,
        'gender_price_delta': float(gender_price_delta),
        'companion_type': companion_type,
        'people_count': people_count,
        'settlement_type': gameplay.settlement_unit,
        'quantity': float(purchase_quantity),
        'unit_price': float(unit_price),
        'total_amount': float(total_amount),
        'pay_amount': float(charged_amount),
        'total_coins': coin_cost,
        'price_source': price_source,
        'trial_requested': trial_requested,
        'remark': remark,
        'addon_ids': addon_ids,
        'addon_value_ids': addon_value_ids,
        'service_value_ids': service_value_ids,
        'value_added_services': selected_addons,
        'addon_value_added_services': selected_addon_values,
        'service_value_added_services': selected_service_values,
        'extra_price_delta': float(extra_price_delta),
        **choice_snapshot,
    }

    # === 扣费前置校验：黑钻是否冻结、是否充足 ===
    if customer.coins_frozen:
        return error_response(msg='黑钻已被冻结，无法下单', code=403)
    if coin_cost > 0 and (customer.coins or 0) < coin_cost:
        return error_response(msg=f'黑钻不足，需要{coin_cost}黑钻，当前仅有{customer.coins or 0}黑钻')

    import random
    order_no = (
        f'SV{timezone.now().strftime("%Y%m%d%H%M%S")}'
        f'{str(user.id).zfill(4)}{random.randint(1000, 9999)}'
    )
    order = Order.objects.create(
        order_no=order_no,
        customer=customer,
        skill=skill,
        status=OrderStatus.PUBLISHED,
        title=f'{skill.name} · {gameplay.name}',
        order_type='self_service',
        duration=duration,
        quantity=people_count,
        purchase_quantity=purchase_quantity,
        settlement_unit=gameplay.settlement_unit,
        self_service_snapshot=snapshot,
        unit_price=unit_price,
        total_amount=total_amount,
        pay_amount=charged_amount,
        game_id=str(skill.game_category_id or ''),
        game_name=game_name,
        remark=remark,
        platform='mini_program',
        assigned_employee=assigned_employee,
    )
    OrderMember.objects.create(
        order=order,
        skill=skill,
        unit_price=unit_price,
        duration=duration,
        amount=charged_amount,
        status='assigned',
        remark=f'{gameplay.name} / {level.name} / {service.name}',
    )

    # === 扣费逻辑：黑钻扣减 + 消费流水 + 财务 Transaction ===
    # 所有订单（包括 0 黑钻订单）都应记录客户订单统计。
    customer.coins = (customer.coins or 0) - coin_cost
    customer.total_amount = (customer.total_amount or Decimal('0')) + charged_amount
    customer.total_orders = (customer.total_orders or 0) + 1
    customer.last_order_date = timezone.now()
    if not customer.first_order_date:
        customer.first_order_date = timezone.now()
    customer.save(update_fields=['coins', 'total_amount', 'total_orders', 'last_order_date', 'first_order_date'])

    if coin_cost > 0:

        # 消费记录
        from apps.customer.models import CustomerConsumeRecord
        CustomerConsumeRecord.objects.create(
            customer=customer,
            order_no=order_no,
            amount=charged_amount,
            type='order',
            remark=f'自助下单 {skill.name}·{gameplay.name}',
        )

        # 财务流水
        wallet, _ = Wallet.objects.get_or_create(user=user, type='user')
        wallet.balance = (wallet.balance or Decimal('0')) - charged_amount
        wallet.total_expense = (wallet.total_expense or Decimal('0')) + charged_amount
        wallet.save(update_fields=['balance', 'total_expense'])
        Transaction.objects.create(
            wallet=wallet,
            order_no=order_no,
            transaction_no=f'TXN{timezone.now().strftime("%Y%m%d%H%M%S")}{user.id:04d}{order.id:04d}',
            type='expense',
            category='self_service_order',
            amount=charged_amount,
            balance_after=wallet.balance,
            remark=f'自助下单扣减 {coin_cost}黑钻',
            operator=request.user if hasattr(request, 'user') else None,
        )

    _mark_preorder_used(checkout_preorder)
    return success_response({
        'order_id': order.id,
        'order_no': order.order_no,
        'total_amount': float(order.total_amount),
        'pay_amount': float(order.pay_amount),
        'total_coins': coin_cost,
        'snapshot': snapshot,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dispatch_hall(request):
    """派单大厅 - 展示所有可接取的订单（自助订单和转单后的订单）"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    game_name = request.GET.get('game_name', '')
    keyword = request.GET.get('keyword', '')

    # 获取当前打手
    current_employee = None
    if request.user.is_authenticated:
        current_employee = request.user.get_active_employee()

    queryset = Order.objects.filter(
        status__in=['published', 'transferring'],
        is_deleted=False
    )

    if game_name:
        queryset = queryset.filter(game_name=game_name)
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword) | Q(remark__icontains=keyword)
        )

    total = queryset.count()
    start = (page - 1) * page_size
    orders = queryset.select_related('customer', 'assigned_employee')[start:start + page_size]

    order_list = []
    for o in orders:
        # 计算剩余席位
        sync_order_seat_state(o)
        if o.status not in ['published', 'transferring']:
            continue
        remaining_slots = get_remaining_slots(o)
        # 只显示还有剩余席位的订单
        if remaining_slots <= 0:
            continue

        # 如果是预约订单，只显示给被预约的打手
        if o.assigned_employee_id and current_employee and o.assigned_employee_id != current_employee.id:
            continue

        # 检查当前打手是否已申请该订单（选秀队列）
        my_claimed = False
        if current_employee:
            candidate = OrderCandidate.objects.filter(
                order=o, employee=current_employee, is_deleted=False
            ).first()
            my_claimed = bool(candidate)

        # 判断是否为预约订单（只能被预约的打手接取）
        is_reserved = bool(o.assigned_employee_id)
        can_claim = not is_reserved or (current_employee and o.assigned_employee_id == current_employee.id)

        # 获取自助订单的服务项
        order_items = []
        if o.order_type == 'self_service':
            for m in o.order_members.filter(is_deleted=False):
                order_items.append({
                    'skill_name': m.skill.name if m.skill else (m.remark or ''),
                    'duration': m.duration,
                    'amount': float(m.amount),
                })

        order_list.append({
            'id': o.id,
            'order_no': o.order_no,
            'title': o.title,
            'status': o.status,
            'game_name': o.game_name,
            'content': o.remark,
            'price': float(o.unit_price),
            'duration': o.duration,
            'quantity': o.quantity,
            'locked_slots': o.locked_slots,
            'remaining_slots': remaining_slots,
            'is_formally_claimed': False,
            'total_amount': float(o.total_amount),
            'customer_name': o.customer.nickname if o.customer else '',
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M'),
            'my_claimed': my_claimed,
            'transfer_reason': o.transfer_reason or '',
            'is_transfer': bool(o.transfer_reason),
            'is_reserved': is_reserved,
            'can_claim': can_claim,
            'assigned_employee_name': o.assigned_employee.nickname if o.assigned_employee else '',
            'order_type': o.order_type,
            'order_items': order_items,
        })

    return success_response({
        'total': len(order_list),
        'page': page,
        'page_size': page_size,
        'list': order_list,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_orders(request):
    """我的订单列表（老板）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return success_response({'total': 0, 'list': []})

    order_status = request.GET.get('status')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # 客户（老板）视角：显示自己的全部订单（含待接单/转单中/已取消）
    queryset = Order.objects.filter(customer=customer, is_deleted=False).order_by('-created_at')

    if order_status:
        queryset = queryset.filter(status=order_status)

    total = queryset.count()
    start = (page - 1) * page_size
    orders = queryset.select_related('skill').prefetch_related(
        'order_members__employee'
    )[start:start + page_size]

    order_list = []
    for o in orders:
        members = []
        for m in o.order_members.filter(is_deleted=False):
            if m.employee is None:
                continue
            members.append({
                'id': m.id,
                'employee_name': m.employee.nickname or m.employee.real_name,
                'employee_avatar': employee_avatar_url(m.employee),
                'status': m.status,
            })
        order_list.append({
            'id': o.id,
            'order_no': o.order_no,
            'skill_name': o.skill.name if o.skill else '',
            'status': o.status,
            'status_display': o.get_status_display(),
            'duration': o.duration,
            'quantity': o.quantity,
            'locked_slots': o.locked_slots,
            'total_amount': float(o.total_amount),
            'pay_amount': float(o.pay_amount),
            'pay_method': o.pay_method,
            'game_name': o.game_name,
            'members': members,
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M'),
            'pay_time': o.pay_time.strftime('%Y-%m-%d %H:%M') if o.pay_time else None,
        })

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': order_list,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_orders(request):
    """陪玩师订单列表 - 只显示已接取的订单"""
    user = request.user
    employee = user.get_active_employee()
    if not employee:
        return error_response(msg='非陪玩师账号')

    order_status = request.GET.get('status')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # 打手视角：显示自己参与（接取/在队）的全部订单，按最新排序。
    # 只要存在未删除的订单成员记录即视为参与，覆盖待确认/待开始/进行中/已完成/已评价/已取消；
    # 排除仍在大厅的 published 与与自己无关的订单。
    queryset = Order.objects.filter(
        order_members__employee=employee,
        order_members__is_deleted=False,
        is_deleted=False
    ).exclude(status='published').distinct().order_by('-created_at')

    if order_status:
        queryset = queryset.filter(status=order_status)

    total = queryset.count()
    start = (page - 1) * page_size
    orders = queryset.select_related('skill').prefetch_related(
        'order_members__employee', 'customer'
    )[start:start + page_size]

    order_list = []
    for o in orders:
        members = []
        for m in o.order_members.filter(is_deleted=False):
            if m.employee is None:
                continue
            members.append({
                'id': m.id,
                'employee_name': m.employee.nickname or m.employee.real_name,
                'employee_avatar': employee_avatar_url(m.employee),
                'status': m.status,
            })
        order_list.append({
            'id': o.id,
            'order_no': o.order_no,
            'skill_name': o.skill.name if o.skill else '',
            'status': o.status,
            'status_display': o.get_status_display(),
            'duration': o.duration,
            'quantity': o.quantity,
            'locked_slots': o.locked_slots,
            'total_amount': float(o.total_amount),
            'pay_amount': float(o.pay_amount),
            'pay_method': o.pay_method,
            'game_name': o.game_name,
            'customer_name': o.customer.nickname if o.customer else '',
            'customer_avatar': field_file_url(o.customer.avatar if o.customer else ''),
            'members': members,
            'created_at': o.created_at.strftime('%Y-%m-%d %H:%M'),
            'pay_time': o.pay_time.strftime('%Y-%m-%d %H:%M') if o.pay_time else None,
        })

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': order_list,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    """订单详情"""
    user = request.user

    # 判断用户类型
    employee = user.get_active_employee()
    is_dasher = bool(employee)

    # 判断是否为客服：优先按角色码判断（与群组等接口一致），
    # 兜底检查 CustomerService 记录（兼容早期未分配 cs 角色的客服账号）
    is_cs = 'cs' in user.get_role_codes()
    if not is_cs:
        try:
            from apps.customer.models import CustomerService
            is_cs = CustomerService.objects.filter(
                customer__user=user, is_deleted=False
            ).exists()
        except Exception:
            is_cs = False

    try:
        if is_cs:
            # 客服可以查看任何未删除的订单
            order = Order.objects.filter(
                id=order_id, is_deleted=False
            ).select_related('skill', 'customer', 'assigned_employee').prefetch_related(
                'order_members__employee', 'comments'
            ).first()
        elif is_dasher:
            # 打手可查看：大厅可接取的订单(published/transferring) + 自己参与的所有订单
            # （含待开始/进行中/已完成/已评价，member 记录存在且未删除即可，不限 member.status）
            order_qs = Order.objects.filter(
                Q(id=order_id) & (
                    Q(status__in=['published', 'transferring']) | Q(
                        order_members__employee=employee,
                        order_members__is_deleted=False,
                    )
                ),
                is_deleted=False
            ).distinct()
            order = order_qs.select_related('skill', 'customer', 'assigned_employee').prefetch_related(
                'order_members__employee', 'comments'
            ).first()
        else:
            # 客户只能查看自己的订单
            customer = user.customer
            order = Order.objects.filter(
                id=order_id, customer=customer, is_deleted=False
            ).select_related('skill', 'customer', 'assigned_employee').prefetch_related(
                'order_members__employee', 'comments'
            ).first()
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    if order is None:
        return error_response(msg='订单不存在')

    sync_order_seat_state(order)
    ensure_order_leader(order)

    # 自动到期检测：以时间为结算单位的订单，到期自动完成
    _auto_complete_order(order)

    members = []
    for m in order.order_members.filter(is_deleted=False):
        if m.employee is None:
            continue
        slots = parse_member_slots(m)
        # 获取该成员的评价
        member_comment = OrderComment.objects.filter(
            order=order, employee=m.employee, is_deleted=False
        ).first()
        members.append({
            'id': m.id,
            'employee_id': m.employee.id,
            'employee_name': m.employee.nickname or m.employee.real_name,
            'employee_avatar': employee_avatar_url(m.employee),
            'skill_name': m.skill.name if m.skill else '',
            'unit_price': float(m.unit_price),
            'duration': m.duration,
            'amount': float(m.amount),
            'slots': slots,
            'status': m.status,
            'status_display': m.get_status_display(),
            'is_leader': m.employee.id == order.leader_id if order.leader else False,
            'has_comment': bool(member_comment),
            'comment_rating': member_comment.rating if member_comment else 0,
            'comment_content': member_comment.content if member_comment else '',
            'comment_images': [img.strip() for img in member_comment.images.split(',') if img.strip()] if (member_comment and member_comment.images) else [],
        })

    comment = None
    comments_qs = order.comments.filter(is_deleted=False)
    if comments_qs.exists():
        c = comments_qs.first()
        # 将逗号分隔的标签字符串转换为数组
        tags_list = [t.strip() for t in c.tags.split(',') if t.strip()] if c.tags else []
        images_list = [img.strip() for img in c.images.split(',') if img.strip()] if c.images else []
        comment = {
            'id': c.id,
            'rating': c.rating,
            'content': c.content,
            'tags': tags_list,
            'images': images_list,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    # 检查当前打手是否已预订该订单
    my_booking = None
    if is_dasher:
        my_booking = OrderMember.objects.filter(
            order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
        ).first()

    # 打手端：是否已在选秀队列
    is_candidate = False
    if is_dasher and order.status == 'published':
        is_candidate = OrderCandidate.objects.filter(
            order=order, employee=employee, is_deleted=False
        ).exists()

    # 构建选秀队列列表（仅客户视角、published 状态）
    candidates = []
    if order.status == 'published':
        for c in order.candidates.filter(is_deleted=False).select_related('employee'):
            if c.employee:
                candidates.append({
                    'id': c.id,
                    'employee_id': c.employee.id,
                    'employee_name': c.employee.nickname or c.employee.real_name,
                    'employee_avatar': employee_avatar_url(c.employee),
                    'applied_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
                })

    # 获取队长信息
    leader_id = order.leader_id if order.leader else None
    action_flags = build_dasher_order_flags(order, employee if is_dasher else None)
    remaining_slots = get_remaining_slots(order)
    my_booking_slots = parse_member_slots(my_booking) if my_booking else 0
    visible_snapshot = dict(order.self_service_snapshot or {})
    if is_dasher:
        is_active_member = any(member['employee_id'] == employee.id for member in members)
        can_view_account = is_active_member or order.assigned_employee_id == employee.id
        if not can_view_account:
            visible_snapshot.pop('game_account_id', None)
            visible_snapshot.pop('game_account_name', None)
            visible_snapshot.pop('game_account_category', None)
    customer_game_account_id = visible_snapshot.get('game_account_id')
    customer_game_account_name = visible_snapshot.get('game_account_name') or ''
    customer_game_account_category = visible_snapshot.get('game_account_category') or ''

    return success_response({
        'id': order.id,
        'order_no': order.order_no,
        'customer_id': order.customer_id,
        'customer_name': order.customer.nickname if order.customer else '',
        'customer_avatar': build_media_url(order.customer.avatar, request) if order.customer else '',
        'customer_display_id': (
            order.customer.user.display_id if order.customer and order.customer.user else ''
        ),
        'skill_name': order.skill.name if order.skill else '',
        'status': order.status,
        'status_display': order.get_status_display(),
        'order_type': order.order_type,
        'duration': order.duration,
        'quantity': order.quantity,
        'purchase_quantity': float(order.purchase_quantity),
        'settlement_unit': order.settlement_unit,
        'self_service_snapshot': visible_snapshot,
        'customer_game_account_id': customer_game_account_id,
        'customer_game_account_name': customer_game_account_name,
        'customer_game_account_category': customer_game_account_category,
        'assigned_employee_id': order.assigned_employee_id,
        'assigned_employee_name': (
            order.assigned_employee.nickname or order.assigned_employee.real_name
        ) if order.assigned_employee else '',
        'assigned_employee_display_id': (
            order.assigned_employee.user.display_id if order.assigned_employee and order.assigned_employee.user else ''
        ),
        'assigned_employee_avatar': employee_avatar_url(order.assigned_employee) if order.assigned_employee else '',
        'locked_slots': order.locked_slots,
        'remaining_slots': remaining_slots,
        'leader_id': leader_id,
        'unit_price': float(order.unit_price),
        'total_amount': float(order.total_amount),
        'discount_amount': float(order.discount_amount),
        'pay_amount': float(order.pay_amount),
        'pay_method': order.pay_method,
        'game_id': order.game_id,
        'game_name': order.game_name,
        'server': order.server,
        'remark': order.remark,
        'cancel_reason': order.cancel_reason,
        'transfer_reason': (order.transfer_reason or '') if is_dasher else '',
        'is_transfer': bool(order.transfer_reason),
        'members': members,
        'candidates': candidates,
        'is_candidate': is_candidate,
        'comment': comment,
        'user_type': 'dasher' if is_dasher else 'customer',
        **action_flags,
        'my_booking': {
            'id': my_booking.id,
            'slots': my_booking_slots,
            'amount': float(my_booking.amount) if my_booking else 0,
        } if my_booking else None,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
        'pay_time': order.pay_time.strftime('%Y-%m-%d %H:%M') if order.pay_time else None,
        'start_time': order.start_time.strftime('%Y-%m-%d %H:%M') if order.start_time else None,
        'end_time': order.end_time.strftime('%Y-%m-%d %H:%M') if order.end_time else None,
        'cancel_time': order.cancel_time.strftime('%Y-%m-%d %H:%M') if order.cancel_time else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def pay_order(request, order_id):
    """支付订单（模拟微信支付）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 当前流程无需支付步骤，订单创建后直接发布
    # 保留此接口兼容旧前端调用
    pay_method = request.data.get('pay_method', 'wechat')
    order.pay_method = pay_method
    order.pay_time = timezone.now()
    order.save(update_fields=['pay_method', 'pay_time', 'updated_at'])

    return success_response(msg='支付成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_order(request, order_id):
    """取消订单（仅限未被接取的订单）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 只允许取消未被接取的订单（published状态且无打手接取）
    if order.status != 'published':
        return error_response(msg='订单已被接取，无法取消')

    # 检查是否有打手已接取
    from apps.order.models import OrderMember
    claimed_count = OrderMember.objects.filter(
        order=order, is_deleted=False,
        status__in=['accepted', 'in_progress']
    ).count()
    if claimed_count > 0:
        return error_response(msg='订单已被打手接取，无法取消')

    reason = request.data.get('reason', '')
    order.status = OrderStatus.CANCELLED
    order.cancel_time = timezone.now()
    order.cancel_reason = reason
    order.save(update_fields=['status', 'cancel_time', 'cancel_reason', 'updated_at'])

    return success_response(msg='取消成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def claim_order(request, order_id):
    """打手申请接取订单（加入选秀队列）
    规则：
    - 打手点击接取后加入选秀队列，不占席位
    - 客户在订单详情页查看选秀队列并挑选打手
    - 被选中的打手成为正式 OrderMember
    """
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态是否可接取
    if order.status != 'published':
        return error_response(msg='订单当前状态不可接取')

    # 如果是预约订单，只有被预约的打手可以接取
    if order.assigned_employee_id and order.assigned_employee_id != employee.id:
        return error_response(msg='该订单为预约订单，仅被预约的打手可以接取')

    # 检查是否已在选秀队列中（含软删除记录，因为唯一索引是物理索引）
    existing_candidate = OrderCandidate.objects.filter(
        order=order, employee=employee
    ).first()
    if existing_candidate and not existing_candidate.is_deleted:
        return error_response(msg='您已在该订单的选秀队列中')

    # 检查是否已是正式成员
    existing_member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()
    if existing_member:
        return error_response(msg='您已经是该订单的打手')

    # 创建或恢复选秀候选人记录
    if existing_candidate and existing_candidate.is_deleted:
        existing_candidate.is_deleted = False
        existing_candidate.save(update_fields=['is_deleted', 'updated_at'])
        candidate = existing_candidate
    else:
        candidate = OrderCandidate.objects.create(order=order, employee=employee)

    # 如果该打手在活跃队伍中，把所有活跃队友也一并加入选秀队列
    team_applied_count = 1  # 已申请人数（含自己）
    my_membership = TeamMember.objects.filter(
        employee=employee, status='active'
    ).select_related('team').first()
    if not order.assigned_employee_id and my_membership and my_membership.team.status:
        teammate_ids = list(
            TeamMember.objects.filter(
                team=my_membership.team, status='active'
            ).exclude(employee=employee)
            .values_list('employee_id', flat=True)
        )
        if teammate_ids:
            # 排除已是正式成员的队友
            already_member_ids = set(OrderMember.objects.filter(
                order=order, employee_id__in=teammate_ids,
                is_deleted=False, status__in=['accepted', 'in_progress']
            ).values_list('employee_id', flat=True))
            # 查询所有已有候选人记录的队友（含软删除，因为唯一索引是物理索引）
            existing_candidates_map = {}  # employee_id -> candidate
            for ec in OrderCandidate.objects.filter(
                order=order, employee_id__in=teammate_ids
            ):
                existing_candidates_map[ec.employee_id] = ec

            # 逐个处理队友：软删除则恢复，无记录则新建，活跃则跳过
            apply_ids = []
            for tid in teammate_ids:
                if tid in already_member_ids:
                    continue  # 已是正式成员，跳过
                ec = existing_candidates_map.get(tid)
                if ec is None:
                    # 完全没记录，需要新建
                    apply_ids.append(tid)
                elif ec.is_deleted:
                    # 软删除记录，恢复
                    ec.is_deleted = False
                    ec.save(update_fields=['is_deleted', 'updated_at'])
                    team_applied_count += 1
                # else: 已在选秀队列（is_deleted=False），跳过

            # 批量新建完全没有记录的队友
            if apply_ids:
                new_candidates = [
                    OrderCandidate(order=order, employee_id=tid) for tid in apply_ids
                ]
                OrderCandidate.objects.bulk_create(new_candidates)
                team_applied_count += len(apply_ids)

    msg = '已加入选秀队列，等待客户挑选'
    if team_applied_count > 1:
        msg = f'已为您及{team_applied_count - 1}位队友加入选秀队列，等待客户挑选'

    return success_response(
        msg=msg,
        data={'candidate_id': candidate.id, 'applied_count': team_applied_count}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def select_candidate(request, order_id):
    """客户从选秀队列中选择打手成为正式成员"""
    user = request.user
    candidate_id = request.data.get('candidate_id')

    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.select_for_update().get(
            id=order_id, customer=customer, is_deleted=False
        )
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    if order.status != 'published':
        return error_response(msg='订单当前状态不可选人')

    remaining = get_remaining_slots(order)
    if remaining <= 0:
        return error_response(msg='订单席位已满')

    try:
        candidate = OrderCandidate.objects.get(
            id=candidate_id, order=order, is_deleted=False
        )
    except OrderCandidate.DoesNotExist:
        return error_response(msg='候选人不存在')

    # 检查是否已是正式成员
    existing = OrderMember.objects.filter(
        order=order, employee=candidate.employee, is_deleted=False,
        status__in=['accepted', 'in_progress']
    ).first()
    if existing:
        return error_response(msg='该打手已是订单成员')

    # 计算金额
    amount_per_slot = order.pay_amount / order.quantity if order.quantity > 0 else 0

    # 创建正式成员
    member = OrderMember.objects.create(
        order=order,
        employee=candidate.employee,
        skill=order.skill,
        unit_price=order.unit_price,
        duration=order.duration,
        amount=round(amount_per_slot, 2),
        status='accepted',
    )

    # 删除候选人记录
    candidate.delete()

    # 同步席位状态
    sync_order_seat_state(order)

    # 选满所有席位后，自动进入确认状态
    actual_members = OrderMember.objects.filter(
        order=order, is_deleted=False, status__in=['accepted', 'in_progress']
    ).count()
    if actual_members >= order.quantity:
        order.status = 'confirming'
        order.save(update_fields=['status', 'updated_at'])

    return success_response(msg='已选中该打手')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_application(request, order_id):
    """打手从选秀队列撤回申请"""
    user = request.user
    try:
        employee = user.get_active_employee()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    candidate = OrderCandidate.objects.filter(
        order=order, employee=employee, is_deleted=False
    ).first()
    if not candidate:
        return error_response(msg='您不在该订单的选秀队列中')

    candidate.delete()
    return success_response(msg='已撤回申请')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_order_member(request, order_id):
    """邀请打手接取订单席位；邀请本身不锁定席位。"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    ensure_order_leader(order)
    if order.status != 'published':
        return error_response(msg='订单已正式接取，不能继续邀请打手')
    if get_remaining_slots(order) <= 0:
        return error_response(msg='订单席位已满，不能继续邀请打手')
    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以邀请打手加入订单')
    if not get_active_order_member(order, employee):
        return error_response(msg='请先接取该订单后再邀请打手')

    target_id = request.data.get('target_id')
    if not target_id:
        return error_response(msg='请选择要邀请的打手')
    try:
        target = Employee.objects.select_related('user').get(id=target_id, is_deleted=False)
    except Employee.DoesNotExist:
        return error_response(msg='目标打手不存在')
    if target.id == employee.id:
        return error_response(msg='不能邀请自己')
    if get_active_order_member(order, target):
        return error_response(msg='该打手已在订单小队中')

    notice = Notice.objects.create(
        title='订单接取邀请',
        content=f'{employee.nickname or employee.real_name} 邀请你接取订单 {order.order_no} 的1个席位，请进入订单详情确认接取。',
        type='order',
        level='info',
        sender=user,
        target_type='user',
        target_ids=str(target.user_id),
        jump_url=f'/pages/order-detail/order-detail?id={order.id}',
        extra=json.dumps({'order_id': order.id, 'invite_from': employee.id, 'target_id': target.id}),
        publish_time=timezone.now(),
    )
    UserNotice.objects.create(notice=notice, user=target.user)
    return success_response(
        msg='邀请已发送，等待该打手接取席位',
        data={'remaining_slots': get_remaining_slots(order)}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def give_up_order(request, order_id):
    """打手放弃订单（释放锁定的席位，返回派单大厅）"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态是否可放弃（in_progress之前都可以放弃）
    if order.status not in ['published', 'confirming', 'claimed']:
        return error_response(msg='订单已开始服务，无法放弃')

    # 查找该打手的订单成员记录
    member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()

    if not member:
        return error_response(msg='您没有接取过该订单')

    is_leader = order.leader_id == employee.id
    is_formal_order = order.status in ['confirming', 'claimed']

    # 队长放弃正式接取的订单 → 删除所有成员，回退到 published
    if is_formal_order and is_leader:
        OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).delete()
        order.status = 'published'
        order.locked_slots = 0
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=[
            'status', 'locked_slots', 'leader', 'customer_confirmed',
            'dasher_confirmed', 'updated_at'
        ])
        return success_response(msg='队长已取消正式接取，订单已回到派单大厅', data={'locked_slots': 0})

    # 释放席位（根据该成员锁定的席位数）
    slots_released = parse_member_slots(member)

    # 更新已锁定席位数
    order.locked_slots = max(0, order.locked_slots - slots_released)

    # 删除订单成员记录
    member.delete()

    # 检查是否还有其他成员
    remaining_members = OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).count()

    if remaining_members == 0:
        # 没有其他成员了，恢复订单状态为 published，清除队长
        order.status = 'published'
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=['status', 'locked_slots', 'leader', 'customer_confirmed', 'dasher_confirmed', 'updated_at'])
    else:
        # 还有其他成员，如果放弃的是队长，需要转移队长
        if is_leader:
            # 找到下一个成员作为队长
            next_member = OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).order_by('id').first()
            if next_member:
                order.leader = next_member.employee
            else:
                order.leader = None
        order.save(update_fields=['locked_slots', 'leader', 'updated_at'])

    return success_response(msg='已放弃', data={'locked_slots': order.locked_slots})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_order(request, order_id):
    """客户确认订单（打手接取后，客户确认变为待开始）"""
    user = request.user

    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, status='confirming', is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在或状态不正确')

    # 客户确认后，订单状态变为 claimed（待开始），打手可以开始服务
    order.status = 'claimed'
    order.customer_confirmed = True
    order.save(update_fields=['status', 'customer_confirmed', 'updated_at'])

    return success_response(msg='确认成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def transfer_order(request, order_id):
    """转单 - 将订单重新投放到派单大厅（只有队长可以转单）"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态是否可转单
    if order.status not in ['in_progress', 'claimed']:
        return error_response(msg='当前订单状态不可转单')

    # 检查是否是该打手的订单
    member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()
    if not member:
        return error_response(msg='您不是该订单的打手')

    transfer_reason = request.data.get('reason', '')
    if not transfer_reason:
        return error_response(msg='请填写转单原因')

    # 转单表示该小队整体退出，订单重新回到派单大厅。
    active_members = list(OrderMember.objects.filter(
        order=order,
        is_deleted=False,
        status__in=ACTIVE_ORDER_MEMBER_STATUSES,
    ).select_related('employee'))
    for active_member in active_members:
        if active_member.employee:
            active_member.employee.status = 'idle'
            active_member.employee.save(update_fields=['status'])
    OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).delete()

    # 更新订单状态为转单中
    order.status = 'transferring'
    order.locked_slots = 0
    order.leader = None
    order.assigned_employee = None
    order.customer_confirmed = False
    order.dasher_confirmed = False
    order.transfer_reason = transfer_reason
    order.save(update_fields=[
        'status', 'locked_slots', 'leader', 'assigned_employee', 'customer_confirmed',
        'dasher_confirmed', 'transfer_reason', 'updated_at'
    ])

    return success_response(msg='转单成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def kick_member(request, order_id):
    """客户踢出订单中的打手（订单开始前）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.select_for_update().get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 只有订单开始前（in_progress之前）才能踢人
    if order.status not in ['published', 'confirming', 'claimed']:
        return error_response(msg='订单已开始，无法踢人')

    member_id = request.data.get('member_id')
    if not member_id:
        return error_response(msg='请选择要踢出的打手')

    try:
        member = OrderMember.objects.get(id=member_id, order=order, is_deleted=False)
    except OrderMember.DoesNotExist:
        return error_response(msg='该打手不在订单中')

    # 记录被踢打手信息
    kicked_name = member.employee.nickname or member.employee.real_name

    # 释放席位
    slots_released = parse_member_slots(member)
    order.locked_slots = max(0, order.locked_slots - slots_released)

    # 删除订单成员记录
    member.delete()

    # 如果被踢的是队长，转移队长
    if order.leader_id == member.employee_id:
        next_member = OrderMember.objects.filter(
            order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
        ).order_by('id').first()
        if next_member:
            order.leader = next_member.employee
        else:
            order.leader = None

    # 如果踢人后没有成员了，恢复订单状态
    remaining_members = OrderMember.objects.filter(
        order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
    ).count()

    if remaining_members == 0:
        order.status = 'published'
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False

    order.save(update_fields=['status', 'locked_slots', 'leader', 'customer_confirmed', 'dasher_confirmed', 'updated_at'])

    # 通知被踢的打手
    try:
        from apps.notice.models import Notice, UserNotice
        notice = Notice.objects.create(
            title='订单移除通知',
            content=f'您已被从订单 {order.order_no} 中移除',
            type='order',
            level='warning',
            sender=user,
            target_type='user',
            target_ids=str(member.employee.user_id),
            jump_url=f'/pages/order-detail/order-detail?id={order.id}',
            publish_time=timezone.now(),
        )
        UserNotice.objects.create(notice=notice, user=member.employee.user)
    except Exception:
        pass

    return success_response(msg=f'已将{kicked_name}从订单中移除')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def discount_order(request, order_id):
    """免单 - 打手对订单部分费用进行免除（只有队长可以免单）"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态
    if order.status not in ['in_progress', 'claimed']:
        return error_response(msg='当前订单状态不可免单')

    # 检查是否是该打手的订单
    member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()
    if not member:
        return error_response(msg='您不是该订单的打手')

    discount_amount = float(request.data.get('amount', 0))
    discount_reason = request.data.get('reason', '')

    if discount_amount <= 0:
        return error_response(msg='免单金额必须大于0')
    if discount_amount > float(order.pay_amount):
        return error_response(msg='免单金额不能超过实付金额')
    if not discount_reason:
        return error_response(msg='请填写免单原因')

    # 更新订单免单信息
    order.discount_amount = discount_amount
    order.discount_reason = discount_reason
    order.pay_amount = float(order.total_amount) - discount_amount
    order.save(update_fields=['discount_amount', 'discount_reason', 'pay_amount', 'updated_at'])

    return success_response(msg='免单成功', data={'pay_amount': float(order.pay_amount)})


def _auto_complete_order(order):
    """
    自动到期检测：以时间为结算单位的订单(start_time + duration)，到期自动完成。
    仅在查看订单详情时触发，幂等操作。
    """
    if order.status != 'in_progress':
        return

    # 仅处理以时间为结算单位的订单
    if order.settlement_unit != 'hour':
        return

    if not order.start_time:
        return

    now = timezone.now()
    elapsed = (now - order.start_time).total_seconds() / 60  # 已过分钟数

    if elapsed >= (order.duration or 0):
        try:
            complete_order_and_settle(order.id, completed_at=now)
        except OrderCompletionError:
            return

        # 更新原始 order 对象的状态（用于后续的响应构建）
        order.status = 'completed'
        order.end_time = now
        order.complete_time = now


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_order(request, order_id):
    """完结订单"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, status='in_progress', is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在或状态不正确')

    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以完结订单')

    try:
        _, settlement = complete_order_and_settle(order.id)
    except OrderCompletionError as exc:
        return error_response(msg=str(exc))

    return success_response(data={
        'settled_count': settlement['settled_count'],
        'commission_total': float(settlement['commission_total']),
        'platform_commission_total': float(settlement['platform_commission_total']),
    }, msg='订单已完结，佣金已结算')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_order(request, order_id):
    """打手开始订单（只有队长可以开始）"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, status='claimed', is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在或状态不正确')

    # 检查是否是队长
    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以开始订单')

    # 检查是否是该打手的订单
    if not order.order_members.filter(employee=employee, is_deleted=False).exists():
        return error_response(msg='您不是该订单的陪玩师')

    if order.locked_slots < order.quantity or order.order_members.filter(is_deleted=False, status='accepted').count() < order.quantity:
        return error_response(msg='多人订单需所有打手就位后才能开始')

    # 更新订单状态为进行中
    order.status = 'in_progress'
    order.start_time = timezone.now()
    order.save(update_fields=['status', 'start_time', 'updated_at'])

    # 更新打手状态为忙碌
    employee.status = 'busy'
    employee.save(update_fields=['status'])

    # 更新订单成员状态
    for member in order.order_members.filter(is_deleted=False):
        member.status = 'in_progress'
        member.start_time = timezone.now()
        member.save(update_fields=['status', 'start_time'])

    _create_order_chat_group(order)

    return success_response(msg='订单已开始')


def _is_cs_user(user):
    """判断用户是否为客服：优先角色码，兜底 CustomerService 记录。"""
    if 'cs' in user.get_role_codes():
        return True
    try:
        from apps.customer.models import CustomerService
        return CustomerService.objects.filter(
            customer__user=user, is_deleted=False
        ).exists()
    except Exception:
        return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_chat_groups(request):
    """当前用户的有效订单群；客服可查看全部订单群，客户/打手仅自己的；查询时清理已到期群。"""
    OrderChatGroup.objects.filter(expires_at__lte=timezone.now()).delete()
    user = request.user
    is_cs = _is_cs_user(user)
    if is_cs:
        groups = OrderChatGroup.objects.filter(
            is_active=True, is_deleted=False,
        ).select_related('order').distinct().order_by('-created_at')
    else:
        groups = OrderChatGroup.objects.filter(
            members__user=user, members__is_deleted=False,
            is_active=True, is_deleted=False,
        ).select_related('order').distinct().order_by('-created_at')
    data = []
    for group in groups:
        last_message = group.messages.filter(is_deleted=False).order_by('-created_at').first()
        data.append({
            'id': group.id, 'name': group.name,
            'title': group.order.title if group.order and group.order.title else group.name,
            'order_id': group.order_id, 'order_no': group.order.order_no,
            'member_count': group.members.filter(is_deleted=False).count(),
            'last_message': last_message.content if last_message else '',
            'last_message_time': last_message.created_at.strftime('%m-%d %H:%M') if last_message else '',
            'expires_at': _as_localtime(group.expires_at).strftime('%Y-%m-%d %H:%M'),
        })
    return success_response(data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def order_chat_group_detail(request, group_id):
    try:
        group = OrderChatGroup.objects.select_related('order').get(id=group_id, is_deleted=False)
    except OrderChatGroup.DoesNotExist:
        return error_response(msg='群组不存在或已删除')
    if group.expires_at <= timezone.now():
        group.delete()
        return error_response(msg='群组已到期并自动删除')
    is_cs = _is_cs_user(request.user)
    if not is_cs and not group.members.filter(user=request.user, is_deleted=False).exists():
        return error_response(msg='您不在该群组中')
    if request.method == 'POST':
        content = str(request.data.get('content', '')).strip()
        if not content:
            return error_response(msg='消息内容不能为空')
        message = OrderChatMessage.objects.create(group=group, sender=request.user, content=content)
        return success_response({'message_id': message.id}, msg='发送成功')
    messages = group.messages.filter(is_deleted=False).select_related('sender')
    order_card = None
    order = group.order if group.order_id else None
    title = group.name
    if order is not None:
        if order.title:
            title = order.title
        members = []
        for m in order.order_members.filter(is_deleted=False):
            if m.employee is None:
                continue
            members.append({
                'id': m.id,
                'employee_name': m.employee.nickname or m.employee.real_name,
                'employee_avatar': employee_avatar_url(m.employee),
            })
        order_card = {
            'order_id': order.id,
            'order_no': order.order_no,
            'skill_name': order.skill.name if order.skill else '',
            'status': order.status,
            'status_display': order.get_status_display(),
            'duration': order.duration,
            'quantity': order.quantity,
            'game_name': order.game_name,
            'total_amount': float(order.total_amount),
            'pay_amount': float(order.pay_amount),
            'members': members,
        }
    return success_response({
        'id': group.id, 'name': title,
        'expires_at': _as_localtime(group.expires_at).strftime('%Y-%m-%d %H:%M'),
        'order_card': order_card,
        'messages': [{
            'id': message.id, 'content': message.content, 'msg_type': message.msg_type,
            'is_mine': message.sender_id == request.user.id,
            'sender_name': (message.sender.nickname or message.sender.username) if message.sender else '系统',
            'created_at': _as_localtime(message.created_at).strftime('%m-%d %H:%M'),
        } for message in messages],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_order(request, order_id):
    """客户结束订单"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, status='in_progress', is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在或状态不正确')

    try:
        _, settlement = complete_order_and_settle(order.id)
    except OrderCompletionError as exc:
        return error_response(msg=str(exc))

    return success_response(data={
        'settled_count': settlement['settled_count'],
        'commission_total': float(settlement['commission_total']),
        'platform_commission_total': float(settlement['platform_commission_total']),
    }, msg='订单已结束，佣金已结算')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_order(request, order_id):
    """评价订单（支持多人订单逐个评价）"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    if order.status not in [OrderStatus.COMPLETED, OrderStatus.REVIEWED]:
        return error_response(msg='订单未完成，无法评价')

    rating = request.data.get('rating', 5)
    content = request.data.get('content', '')
    tags = request.data.get('tags', '')
    is_anonymous = request.data.get('is_anonymous', False)
    member_id = request.data.get('member_id')
    images = request.data.get('images', '')
    # images 可以是逗号分隔的字符串或列表
    if isinstance(images, list):
        images = ','.join(images)

    # 评价对象必须来自已绑定真实打手的成员记录。创建订单时可能存在一条
    # employee 为空的占位记录，不能用 order_members.first() 直接取。
    reviewable_members = order.order_members.filter(
        is_deleted=False, employee__isnull=False
    ).select_related('employee')
    if member_id:
        try:
            member = reviewable_members.get(id=member_id)
        except OrderMember.DoesNotExist:
            return error_response(msg='订单成员不存在')
    else:
        if reviewable_members.count() > 1:
            return error_response(msg='多人订单需要指定评价的打手')
        member = reviewable_members.first()
    employee = member.employee if member else None

    # 检查是否已经评价过该打手
    if not employee:
        return error_response(msg='评价的打手不存在')

    existing_qs = OrderComment.objects.filter(order=order, is_deleted=False)
    if member:
        existing_qs = existing_qs.filter(
            Q(member=member) | Q(member__isnull=True, employee=employee)
        )
    else:
        existing_qs = existing_qs.filter(employee=employee)
    existing = existing_qs.first()

    if existing:
        # 更新已有评价
        existing.rating = rating
        existing.content = content
        existing.tags = tags
        existing.is_anonymous = is_anonymous
        existing.images = images
        existing.save()
        comment = existing
    else:
        comment = create_order_comment_with_retry(
            order=order,
            member=member,
            customer=customer,
            employee=employee,
            rating=rating,
            content=content,
            tags=tags,
            is_anonymous=is_anonymous,
            images=images,
        )

    # 检查是否所有打手都已评价
    total_members = order.order_members.filter(
        is_deleted=False, employee__isnull=False
    ).values('employee').distinct().count()
    reviewed_count = OrderComment.objects.filter(
        order=order, is_deleted=False
    ).values('employee').distinct().count()

    if reviewed_count >= total_members:
        order.status = OrderStatus.REVIEWED
        order.save(update_fields=['status', 'updated_at'])

    # 更新陪玩师评分
    if employee:
        from django.db.models import Avg
        avg = OrderComment.objects.filter(employee=employee, is_deleted=False).aggregate(avg=Avg('rating'))['avg']
        if avg:
            employee.rating = round(avg, 2)
            employee.save(update_fields=['rating'])

    return success_response(msg='评价成功')


# ============ 消息模块 ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_notices(request):
    """我的消息列表"""
    user = request.user
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    queryset = UserNotice.objects.filter(
        user=user, is_deleted=False
    ).select_related('notice').order_by('-created_at')

    total = queryset.count()
    start = (page - 1) * page_size
    notices = queryset[start:start + page_size]

    notice_list = []
    for n in notices:
        notice_list.append({
            'id': n.id,
            'title': n.notice.title if n.notice else '',
            'content': n.notice.content if n.notice else '',
            'type': n.notice.type if n.notice else '',
            'level': n.notice.level if n.notice else '',
            'is_read': n.is_read,
            'extra': n.notice.extra if n.notice else '',
            'jump_url': n.notice.jump_url if n.notice else '',
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    official_conversation = None
    latest_announcement = Announcement.objects.filter(
        status=True, is_deleted=False
    ).order_by('sort', '-created_at').first()
    if latest_announcement:
        official_conversation = {
            'id': 'official-announcements',
            'title': '官方公告',
            'content': latest_announcement.title or latest_announcement.content,
            'type': 'official',
            'level': 'info',
            'is_read': True,
            'is_official': True,
            'is_pinned': True,
            'image': build_media_url(latest_announcement.image, request),
            'created_at': latest_announcement.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': notice_list,
        'official_conversation': official_conversation,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def official_announcements(request):
    """官方公告列表"""
    queryset = Announcement.objects.filter(
        status=True, is_deleted=False
    ).order_by('sort', '-created_at')
    serializer = AnnouncementSerializer(queryset, many=True, context={'request': request})
    return success_response({
        'total': queryset.count(),
        'list': serializer.data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """未读消息数"""
    user = request.user
    count = UserNotice.objects.filter(user=user, is_read=False, is_deleted=False).count()
    return success_response({'count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, notice_id):
    """标记已读"""
    user = request.user
    try:
        notice = UserNotice.objects.get(id=notice_id, user=user, is_deleted=False)
        notice.is_read = True
        notice.read_time = timezone.now()
        notice.save(update_fields=['is_read', 'read_time'])
    except UserNotice.DoesNotExist:
        pass
    return success_response(msg='已读')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """全部已读"""
    user = request.user
    UserNotice.objects.filter(user=user, is_read=False, is_deleted=False).update(
        is_read=True, read_time=timezone.now()
    )
    return success_response(msg='全部已读')


# ============ 礼物模块 ============

@api_view(['GET'])
@permission_classes([AllowAny])
def gift_list(request):
    """礼物列表"""
    gifts = Gift.objects.filter(status=True)
    return success_response(GiftSerializer(gifts, many=True).data)


# ============ 客服配置 ============

@api_view(['GET'])
@permission_classes([AllowAny])
def customer_service(request):
    """获取客服联系方式（根据当天排班）"""
    from apps.system.models import Config
    from apps.schedule.models import CSSchedule

    phone = ''
    wechat = ''
    work_time = '9:00-22:00'

    try:
        phone_config = Config.objects.filter(key='cs_phone').first()
        if phone_config:
            phone = phone_config.value
    except Exception:
        pass

    try:
        wechat_config = Config.objects.filter(key='cs_wechat').first()
        if wechat_config:
            wechat = wechat_config.value
    except Exception:
        pass

    # 获取今天的星期（0=周一，6=周日）
    today = timezone.now().weekday()

    # 获取今天的客服排班
    cs_schedule = CSSchedule.objects.filter(day_of_week=today, status=True).select_related('employee').first()
    if cs_schedule:
        work_time = f"{cs_schedule.start_time.strftime('%H:%M')}-{cs_schedule.end_time.strftime('%H:%M')}"

    try:
        work_time_config = Config.objects.filter(key='cs_work_time').first()
        if work_time_config and not cs_schedule:
            work_time = work_time_config.value
    except Exception:
        pass

    return success_response({
        'phone': phone,
        'wechat': wechat,
        'work_time': work_time,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def cs_welcome_message(request):
    """获取客服欢迎语"""
    from apps.system.models import CSWelcomeConfig
    welcome_text = ''
    questions = []
    try:
        config = CSWelcomeConfig.objects.filter(is_deleted=False, is_enabled=True).first()
        welcome_text = config.welcome_text if config else ''
        from apps.system.models import CSKeywordRule
        rules = CSKeywordRule.objects.filter(
            is_deleted=False, is_enabled=True
        ).order_by('sort', 'id')
        questions = [
            {'id': rule.id, 'question': rule.keyword, 'answer': rule.reply_text}
            for rule in rules
        ]
    except Exception:
        pass
    return success_response({'welcome_text': welcome_text, 'questions': questions})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_human_service(request):
    """客户转人工：按当前排班广播给所有可接入客服。"""
    from apps.customer.models import CustomerServiceConversation

    try:
        customer = request.user.customer
    except Exception:
        return error_response(msg='客户资料不存在')

    existing = CustomerServiceConversation.objects.filter(
        customer=customer,
        status__in=[CustomerServiceConversation.STATUS_WAITING, CustomerServiceConversation.STATUS_ACTIVE],
        is_deleted=False,
    ).select_related('handler').first()
    if existing:
        return success_response({
            'conversation_id': existing.id,
            'status': existing.status,
            'handler_name': (existing.handler.nickname or existing.handler.username) if existing.handler else '',
        }, msg='人工客服请求已提交')

    duty_users = _current_duty_cs_users()
    if not duty_users:
        return error_response(msg='当前暂无排班客服，请稍后再试')
    conversation = CustomerServiceConversation.objects.create(
        customer=customer,
        eligible_user_ids=[user.id for user in duty_users],
    )
    notice = Notice.objects.create(
        title='新的人工客服请求',
        content=f'客户“{customer.nickname}”正在等待人工客服接入，点击后可接入处理。',
        type='system', level='warning', target_type='user',
        target_ids=','.join(str(user.id) for user in duty_users),
        extra=json.dumps({'type': 'cs_request', 'conversation_id': conversation.id}),
        publish_time=timezone.now(),
    )
    UserNotice.objects.bulk_create([UserNotice(notice=notice, user=user) for user in duty_users])
    return success_response({
        'conversation_id': conversation.id,
        'status': conversation.status,
    }, msg='已通知当前值班客服')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def human_service_status(request):
    from apps.customer.models import CustomerServiceConversation
    try:
        customer = request.user.customer
    except Exception:
        return error_response(msg='客户资料不存在')
    conversation = CustomerServiceConversation.objects.filter(
        customer=customer, is_deleted=False,
        status__in=[CustomerServiceConversation.STATUS_WAITING, CustomerServiceConversation.STATUS_ACTIVE],
    ).select_related('handler').first()
    if not conversation:
        return success_response({'status': 'bot'})
    return success_response({
        'conversation_id': conversation.id,
        'status': conversation.status,
        'handler_name': (conversation.handler.nickname or conversation.handler.username) if conversation.handler else '',
    })


def _check_keyword_auto_reply(content):
    """检查客户消息是否匹配关键词，返回自动回复内容"""
    from apps.system.models import CSKeywordRule
    if not content:
        return None
    try:
        rules = CSKeywordRule.objects.filter(is_deleted=False, is_enabled=True).order_by('sort', 'id')
        for rule in rules:
            keyword = rule.keyword.strip()
            if not keyword:
                continue
            matched = False
            if rule.match_type == 'exact':
                matched = content.strip() == keyword
            elif rule.match_type == 'startswith':
                matched = content.strip().startswith(keyword)
            else:  # contains
                matched = keyword in content
            if matched:
                return rule.reply_text
    except Exception:
        pass
    return None


# ============ 客服对话 ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_cs_message(request):
    """发送客服消息"""
    from apps.customer.models import Customer, CSMessage

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    content = request.data.get('content', '')
    msg_type = request.data.get('msg_type', 'text')
    ticket_id = request.data.get('ticket_id')

    if not content:
        return error_response(msg='消息内容不能为空')

    # 获取关联工单
    ticket = None
    if ticket_id:
        from apps.order.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(id=ticket_id, customer=customer)
        except SupportTicket.DoesNotExist:
            pass

    # 客户发送消息时不绑定客服，等客服回复时再绑定
    try:
        message = CSMessage.objects.create(
            customer=customer,
            cs_user=None,
            ticket=ticket,
            content=content,
            msg_type=msg_type,
            sender_type='customer',
        )
    except Exception:
        message = CSMessage.objects.create(
            customer=customer,
            cs_user=None,
            content=content,
            msg_type=msg_type,
            sender_type='customer',
        )

    if ticket and msg_type == 'text':
        _ensure_ticket_order_card_message(customer, ticket)

    # 关键词自动回复
    auto_reply_content = None
    if msg_type == 'text':
        auto_reply_content = _check_keyword_auto_reply(content)
    if auto_reply_content:
        try:
            CSMessage.objects.create(
                customer=customer,
                cs_user=None,
                ticket=ticket,
                content=auto_reply_content,
                msg_type='text',
                sender_type='cs',
            )
        except Exception:
            CSMessage.objects.create(
                customer=customer,
                cs_user=None,
                content=auto_reply_content,
                msg_type='text',
                sender_type='cs',
            )

    return success_response(msg='发送成功', data={'message_id': message.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_messages(request):
    """????????"""
    from apps.customer.models import CSMessage

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='?????')

    ticket_id = request.GET.get('ticket_id')
    base_only_fields = ['id', 'customer', 'cs_user', 'content', 'msg_type', 'is_read', 'sender_type', 'created_at']

    if _cs_message_has_ticket_column():
        queryset = CSMessage.objects.filter(customer=customer).only(
            *(base_only_fields + ['ticket'])
        )
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        else:
            queryset = queryset.filter(ticket__isnull=True)
        messages = queryset.select_related('cs_user', 'ticket__order').order_by('created_at')
    else:
        queryset = CSMessage.objects.filter(customer=customer).only(*base_only_fields)
        messages = queryset.select_related('cs_user').order_by('created_at')

    data = [_serialize_cs_message(msg) for msg in messages]

    messages.filter(sender_type='cs', is_read=False).update(is_read=True)

    return success_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_unread_count(request):
    """获取客服未读消息数"""
    from apps.customer.models import CSMessage

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    count = CSMessage.objects.filter(customer=customer, sender_type='cs', is_read=False).count()
    return success_response({'count': count})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_chat_list(request):
    """获取客服工单聊天列表"""
    from apps.customer.models import CSMessage, CustomerService, CustomerServiceConversation

    user = request.user
    try:
        cs = CustomerService.objects.get(customer__user=user)
    except CustomerService.DoesNotExist:
        return error_response(msg='您不是客服')

    has_ticket_column = _cs_message_has_ticket_column()

    chat_list = []
    tickets = SupportTicket.objects.filter(
        is_deleted=False,
        status__in=[SupportTicket.TicketStatus.OPEN, SupportTicket.TicketStatus.IN_PROGRESS],
    ).select_related(
        'customer', 'order', 'handler'
    ).order_by('-created_at')

    for ticket in tickets:
        if has_ticket_column:
            thread_messages = CSMessage.objects.filter(customer=ticket.customer, ticket_id=ticket.id)
        else:
            thread_messages = CSMessage.objects.none()

        last_msg = thread_messages.only(
            'id', 'customer', 'content', 'created_at', 'sender_type', 'is_read'
        ).order_by('-created_at').first()
        unread_count = thread_messages.filter(sender_type='customer', is_read=False).count()
        sort_dt = last_msg.created_at if last_msg else ticket.created_at

        customer_avatar = ''
        if ticket.customer and ticket.customer.avatar:
            avatar_str = str(ticket.customer.avatar)
            if avatar_str.startswith('http'):
                customer_avatar = avatar_str
            else:
                customer_avatar = str(ticket.customer.avatar) if ticket.customer.avatar else ''

        chat_list.append({
            'chat_key': f'ticket-{ticket.id}',
            'customer_id': ticket.customer.id if ticket.customer else None,
            'customer_name': ticket.customer.nickname if ticket.customer else '',
            'customer_avatar': customer_avatar,
            'ticket_id': ticket.id,
            'ticket_no': ticket.ticket_no,
            'ticket_title': ticket.title,
            'last_message': last_msg.content if last_msg else ticket.description,
            'last_message_time': last_msg.created_at.strftime('%H:%M') if last_msg else ticket.created_at.strftime('%H:%M'),
            'sort_time': sort_dt,
            'unread_count': unread_count,
        })

    conversations = CustomerServiceConversation.objects.filter(
        is_deleted=False,
        status__in=[CustomerServiceConversation.STATUS_WAITING, CustomerServiceConversation.STATUS_ACTIVE],
    ).select_related('customer', 'handler')
    for conversation in conversations:
        if conversation.handler_id and conversation.handler_id != user.id:
            continue
        if not conversation.handler_id and user.id not in (conversation.eligible_user_ids or []):
            continue
        last_msg = CSMessage.objects.filter(
            customer=conversation.customer, ticket__isnull=True
        ).order_by('-created_at').first()
        chat_list.append({
            'chat_key': f'conversation-{conversation.id}',
            'customer_id': conversation.customer_id,
            'customer_name': conversation.customer.nickname,
            'customer_avatar': str(conversation.customer.avatar or ''),
            'conversation_id': conversation.id,
            'conversation_status': conversation.status,
            'last_message': last_msg.content if last_msg else '客户申请转人工服务',
            'last_message_time': (last_msg.created_at if last_msg else conversation.requested_at).strftime('%H:%M'),
            'sort_time': last_msg.created_at if last_msg else conversation.requested_at,
            'unread_count': CSMessage.objects.filter(
                customer=conversation.customer, ticket__isnull=True,
                sender_type='customer', is_read=False,
            ).count(),
        })

    # 按最后消息时间排序
    chat_list.sort(key=lambda x: x['sort_time'], reverse=True)

    for item in chat_list:
        item.pop('sort_time', None)

    return success_response(chat_list)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_chat_messages(request):
    """获取客服聊天消息"""
    from apps.customer.models import CSMessage, Customer

    customer_id = request.GET.get('customer_id')
    ticket_id = request.GET.get('ticket_id')
    conversation_id = request.GET.get('conversation_id')

    if not customer_id:
        return error_response(msg='缺少客户ID')

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return error_response(msg='客户不存在')

    base_only_fields = ['id', 'customer', 'cs_user', 'content', 'msg_type', 'is_read', 'sender_type', 'created_at']

    if _cs_message_has_ticket_column():
        queryset = CSMessage.objects.filter(customer=customer).only(
            *(base_only_fields + ['ticket'])
        )
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        else:
            queryset = queryset.filter(ticket__isnull=True)
        messages = queryset.select_related('cs_user', 'ticket__order').order_by('created_at')
    else:
        queryset = CSMessage.objects.filter(customer=customer).only(*base_only_fields)
        messages = queryset.select_related('cs_user').order_by('created_at')

    data = [_serialize_cs_message(msg) for msg in messages]

    messages.filter(sender_type='customer', is_read=False).update(is_read=True)

    customer_avatar = ''
    if customer.avatar:
        avatar_str = str(customer.avatar)
        if avatar_str.startswith('http'):
            customer_avatar = avatar_str
        else:
            customer_avatar = str(customer.avatar) if customer.avatar else ''

    return success_response({
        'messages': data,
        'customer_avatar': customer_avatar,
        'ticket': _get_ticket_order_brief(ticket_id) if ticket_id else None,
        'conversation_id': int(conversation_id) if conversation_id else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_human_service(request, conversation_id):
    """客服原子接入会话；已有处理人时禁止其他客服抢占。"""
    from apps.customer.models import CustomerService, CustomerServiceConversation, CSMessage
    try:
        CustomerService.objects.get(customer__user=request.user, is_deleted=False)
    except CustomerService.DoesNotExist:
        return error_response(msg='您不是客服')

    with transaction.atomic():
        try:
            conversation = CustomerServiceConversation.objects.select_for_update().select_related('customer').get(
                id=conversation_id, is_deleted=False
            )
        except CustomerServiceConversation.DoesNotExist:
            return error_response(msg='会话不存在')
        if conversation.handler_id and conversation.handler_id != request.user.id:
            return error_response(msg='该客户已由其他客服接入')
        if request.user.id not in (conversation.eligible_user_ids or []) and not conversation.handler_id:
            return error_response(msg='您不在本次排班接待范围内')
        if not conversation.handler_id:
            conversation.handler = request.user
            conversation.status = CustomerServiceConversation.STATUS_ACTIVE
            conversation.accepted_at = timezone.now()
            conversation.save(update_fields=['handler', 'status', 'accepted_at', 'updated_at'])
            handler_name = request.user.nickname or request.user.username
            CSMessage.objects.create(
                customer=conversation.customer, cs_user=request.user,
                content=f'客服 {handler_name} 已接入，正在为您处理。',
                msg_type='text', sender_type='cs',
            )
    return success_response({
        'conversation_id': conversation.id,
        'handler_name': request.user.nickname or request.user.username,
    }, msg='接入成功')


def _get_ticket_order_brief(ticket_id):
    """获取工单关联订单的简要信息（供客服聊天页判断按钮显示）"""
    try:
        ticket = SupportTicket.objects.select_related('order').get(id=ticket_id)
    except SupportTicket.DoesNotExist:
        return None
    order = ticket.order
    if order is None:
        return None
    return {
        'ticket_id': ticket.id,
        'ticket_no': ticket.ticket_no,
        'ticket_status': ticket.status,
        'order_id': order.id,
        'order_no': order.order_no,
        'order_status': order.status,
        'order_status_display': order.get_status_display(),
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_cs_reply(request):
    """客服回复消息"""
    from apps.customer.models import CSMessage, Customer, CustomerService

    user = request.user
    logger.info(f'客服回复消息: user_id={user.id}')

    try:
        cs = CustomerService.objects.get(customer__user=user)
        logger.info(f'找到客服记录: cs_id={cs.id}')
    except CustomerService.DoesNotExist:
        logger.error(f'用户{user.id}不是客服')
        return error_response(msg='您不是客服')

    customer_id = request.data.get('customer_id')
    content = request.data.get('content', '')
    ticket_id = request.data.get('ticket_id')
    conversation_id = request.data.get('conversation_id')
    logger.info(f'收到消息: customer_id={customer_id}, content={content}, ticket_id={ticket_id}')

    if not customer_id:
        return error_response(msg='缺少客户ID')
    if not content:
        return error_response(msg='消息内容不能为空')

    try:
        customer = Customer.objects.get(id=customer_id)
        logger.info(f'找到客户: customer_id={customer.id}')
    except Customer.DoesNotExist:
        logger.error(f'客户{customer_id}不存在')
        return error_response(msg='客户不存在')

    # 获取关联工单
    if conversation_id:
        from apps.customer.models import CustomerServiceConversation
        conversation = CustomerServiceConversation.objects.filter(
            id=conversation_id, customer=customer, is_deleted=False
        ).first()
        if not conversation or conversation.handler_id != user.id:
            return error_response(msg='请先接入该人工客服会话')

    ticket = None
    if ticket_id:
        from apps.order.models import SupportTicket
        try:
            ticket = SupportTicket.objects.get(id=ticket_id)
        except SupportTicket.DoesNotExist:
            pass

    try:
        message = CSMessage.objects.create(
            customer=customer,
            cs_user=user,
            ticket=ticket,
            content=content,
            msg_type='text',
            sender_type='cs',
        )
    except Exception:
        # ticket_id列不存在时，退化为不带ticket的创建
        message = CSMessage.objects.create(
            customer=customer,
            cs_user=user,
            content=content,
            msg_type='text',
            sender_type='cs',
        )
    logger.info(f'消息已保存: message_id={message.id}')

    # 将该客户的消息绑定到当前客服（确保会话一致）
    update_kwargs = {'cs_user': user}
    filter_kwargs = {'customer': customer, 'sender_type': 'customer'}
    try:
        if ticket_id:
            filter_kwargs['ticket_id'] = ticket_id
        CSMessage.objects.filter(**filter_kwargs).update(**update_kwargs)
    except Exception:
        CSMessage.objects.filter(customer=customer, sender_type='customer').update(**update_kwargs)

    return success_response(msg='发送成功', data={'message_id': message.id})


# ============ 个人中心 ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """用户信息"""
    user = request.user
    related = get_related_profile_objects(user)
    nickname = choose_display_nickname(
        user,
        wx_user=related['wx_user'],
        customer=related['customer'],
        employee=related['employee'],
    )
    avatar = (
        related['wx_user'].avatar if related['wx_user'] else ''
    ) or field_file_url(user.avatar) or field_file_url(related['customer'].avatar if related['customer'] else '') or field_file_url(related['employee'].avatar if related['employee'] else '')
    phone = (
        related['wx_user'].phone if related['wx_user'] else ''
    ) or user.phone or (related['customer'].phone if related['customer'] else '') or (related['employee'].phone if related['employee'] else '')

    # 判断用户类型
    user_type = 'customer'
    employee_obj = related['employee']
    customer_obj = related['customer']
    is_cs = False
    try:
        if customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
            is_cs = True
    except Exception:
        is_cs = False
    try:
        if employee_obj:
            user_type = 'dasher'
        elif is_cs:
            user_type = 'cs'
    except Exception:
        pass

    work_status = 'off_duty'
    if user_type == 'dasher' and employee_obj:
        work_status = employee_obj.work_status
    elif user_type == 'cs' and is_cs:
        work_status = customer_obj.cs_profile.work_status

    # 统计数据
    order_count = 0
    total_spent = 0
    balance = 0
    coins = 0
    is_busy = False
    if user_type == 'customer':
        try:
            customer = user.customer
            order_count = Order.objects.filter(customer=customer, is_deleted=False).count()
            total_spent = float(
                Order.objects.filter(
                    customer=customer,
                    status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
                    is_deleted=False
                ).values_list('pay_amount', flat=True)
            ) or 0
            balance = float(customer.balance) if customer.balance else 0
            coins = int(customer.coins) if customer.coins else 0
        except Exception:
            order_count = 0
            total_spent = 0
            balance = 0
            coins = 0
    elif user_type == 'dasher' and employee_obj:
        order_count = employee_obj.order_count if employee_obj else 0
        # 检查是否有进行中的订单
        has_in_progress = Order.objects.filter(
            order_members__employee=employee_obj,
            order_members__is_deleted=False,
            order_members__status='in_progress',
            status='in_progress',
            is_deleted=False
        ).exists()
        is_busy = has_in_progress
        # 更新员工状态
        if employee_obj.status != ('busy' if is_busy else 'idle'):
            employee_obj.status = 'busy' if is_busy else 'idle'
            employee_obj.save(update_fields=['status'])

    # 获取打手标签
    tags = []
    if employee_obj:
        tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in employee_obj.tags.filter(status=True)]

    return success_response({
        'id': user.id,
        'nickname': nickname,
        'avatar': avatar,
        'phone': phone,
        'gender': user.gender or 'unknown',
        'user_type': user_type,
        'order_count': order_count,
        'total_spent': round(total_spent, 2),
        'balance': round(balance, 2),
        'coins': coins,
        'customer_id': customer_obj.id if customer_obj else None,
        'is_busy': is_busy,
        'status': 'busy' if is_busy else 'idle',
        'work_status': work_status,
        'level_num': employee_obj.level_num if employee_obj else 0,
        'intro': employee_obj.intro if employee_obj else '',
        'voice_intro': build_media_url(employee_obj.voice_intro, request) if employee_obj and employee_obj.voice_intro else '',
        'voice_duration': employee_obj.voice_duration if employee_obj else 0,
        'commission_balance': float(employee_obj.commission_balance) if employee_obj else 0,
        'tags': tags,
        'photos': employee_obj.photos if employee_obj else [],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """更新用户信息"""
    import logging
    logger = logging.getLogger(__name__)
    
    user = request.user
    nickname = request.data.get('nickname')
    avatar = request.data.get('avatar')
    intro = request.data.get('intro')
    gender = request.data.get('gender')
    voice_intro = request.data.get('voice_intro')
    voice_upload_id = request.data.get('voice_upload_id')
    remove_voice = request.data.get('remove_voice') is True
    voice_duration = request.data.get('voice_duration')
    tags = request.data.get('tags')
    
    logger.info(
        f'Update profile: user={user.id}, nickname={nickname!r}, gender={gender!r}, '
        f'avatar={bool(avatar)}, voice_upload_id={voice_upload_id!r}, '
        f'remove_voice={remove_voice}, voice_dur={voice_duration!r}, '
        f'tags={tags}'
    )

    # 如果是打手，保存个人介绍、语音、标签
    employee = user.get_active_employee() if hasattr(user, 'get_active_employee') else None
    if employee:
        # 新录音必须引用当前用户刚上传的音频记录，不能信任客户端传入的任意 URL。
        voice_upload = None
        if voice_upload_id is not None:
            voice_upload = UploadFile.objects.filter(
                pk=voice_upload_id,
                uploader=user,
                category='audio',
                is_deleted=False,
            ).first()
            if not voice_upload or not voice_upload.url:
                return error_response(msg='语音上传记录无效，请重新录制')
        elif voice_intro:
            # 兼容尚未更新的小程序版本，但仍校验 URL 属于当前用户的音频上传记录。
            voice_upload = UploadFile.objects.filter(
                url=voice_intro,
                uploader=user,
                category='audio',
                is_deleted=False,
            ).first()
            if not voice_upload:
                return error_response(msg='语音上传记录无效，请重新录制')

        parsed_voice_duration = None
        if voice_upload:
            try:
                parsed_voice_duration = int(voice_duration)
            except (TypeError, ValueError):
                return error_response(msg='语音时长无效，请重新录制')
            if parsed_voice_duration < 1 or parsed_voice_duration > 10:
                return error_response(msg='语音时长必须为1到10秒')
        elif remove_voice or voice_intro == '':
            parsed_voice_duration = 0

        if intro is not None:
            employee.intro = intro
        if parsed_voice_duration is not None:
            employee.voice_duration = parsed_voice_duration

        try:
            with transaction.atomic():
                sync_profile_tables(user, nickname=nickname, avatar=avatar, gender=gender)
                update_fields = []
                if voice_upload:
                    employee.voice_intro = voice_upload.url
                    update_fields.extend(['voice_intro', 'voice_duration'])
                    if voice_upload.duration != parsed_voice_duration:
                        voice_upload.duration = parsed_voice_duration
                        voice_upload.save(update_fields=['duration', 'updated_at'])
                elif remove_voice or voice_intro == '':
                    employee.voice_intro = ''
                    update_fields.extend(['voice_intro', 'voice_duration'])

                if intro is not None:
                    update_fields.append('intro')
                if update_fields:
                    employee.save(update_fields=list(dict.fromkeys(update_fields)))

                if tags is not None:
                    employee.tags.set(tags)
        except Exception as e:
            logger.exception('update_profile employee data save failed: %s', e)
            return error_response(msg='个人资料保存失败，请重试')

        employee.refresh_from_db(fields=['voice_intro', 'voice_duration', 'intro'])
        return success_response({
            'voice_intro': build_media_url(employee.voice_intro, request) if employee.voice_intro else '',
            'voice_duration': employee.voice_duration or 0,
        }, msg='更新成功')

    sync_profile_tables(user, nickname=nickname, avatar=avatar, gender=gender)
    return success_response(msg='更新成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_employee_photo(request):
    """打手上传照片到个人照片墙"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    if 'file' not in request.FILES:
        return error_response(msg='请选择照片')

    file_obj = request.FILES['file']
    if file_obj.size > 10 * 1024 * 1024:
        return error_response(msg='照片大小不能超过10MB')

    # 验证图片类型
    import os
    ext = os.path.splitext(file_obj.name)[1].lower()
    allowed_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    if ext not in allowed_exts:
        return error_response(msg='不支持的图片格式，请上传 JPG/PNG/GIF/WEBP')

    # 上传到 COS 或本地
    from apps.upload.views import upload_to_cos
    from apps.upload.models import UploadFile
    import hashlib
    from datetime import date

    md5_hash = hashlib.md5()
    for chunk in file_obj.chunks():
        md5_hash.update(chunk)
    file_obj.seek(0)
    md5 = md5_hash.hexdigest()

    today = date.today().strftime('%Y/%m/%d')
    file_path = f'uploads/{today}/{md5}{ext}'

    use_cos = bool(settings.COS_SECRET_ID and settings.COS_SECRET_KEY and settings.COS_BUCKET)
    if use_cos:
        try:
            full_url = upload_to_cos(file_obj, file_path)
            storage_type = 'cos'
        except Exception as e:
            logger.exception('COS upload failed: %s', e)
            return error_response(msg='照片上传失败，请重试')
    else:
        from django.core.files.storage import default_storage
        local_path = default_storage.save(file_path, file_obj)
        full_url = f'{request.scheme}://{request.get_host()}/media/{local_path}'
        storage_type = 'local'

    UploadFile.objects.create(
        file_name=file_obj.name,
        file_size=file_obj.size,
        file_type='image',
        mime_type=getattr(file_obj, 'content_type', '') or 'image/jpeg',
        md5=md5,
        uploader=user,
        category='employee_photo',
        storage_type=storage_type,
        url=full_url,
    )

    # 更新 Employee.photos
    photos = list(employee.photos or [])
    photos.append(full_url)
    employee.photos = photos
    employee.save(update_fields=['photos', 'updated_at'])

    return success_response({
        'url': full_url,
        'photos': photos,
    }, msg='上传成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_employee_photo(request):
    """打手删除照片墙中的某张照片"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    photo_url = request.data.get('url', '').strip()
    if not photo_url:
        return error_response(msg='请指定要删除的照片')

    photos = list(employee.photos or [])
    if photo_url not in photos:
        return error_response(msg='照片不存在')

    photos.remove(photo_url)
    employee.photos = photos
    employee.save(update_fields=['photos', 'updated_at'])

    return success_response({
        'photos': photos,
    }, msg='已删除')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_skills(request):
    """获取打手自己的技能设置"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    relations = EmployeeSkillRelation.objects.filter(
        employee=employee, is_deleted=False, skill__status=True
    ).select_related(
        'skill', 'skill__game_category', 'skill__required_rank'
    ).order_by('-is_enabled', 'skill__sort', 'id')
    my_skills = []
    for rel in relations:
        my_skills.append({
            'id': rel.id,
            'skill_id': rel.skill.id,
            'name': rel.skill.name,
            'category': rel.skill.category,
            'game_name': rel.skill.game_category.name if rel.skill.game_category else '',
            'game_id': rel.skill.game_category.id if rel.skill.game_category else 0,
            'required_rank_id': rel.skill.required_rank_id or 0,
            'required_rank_name': rel.skill.required_rank.name if rel.skill.required_rank else '',
            'level_name': rel.skill.required_rank.name if rel.skill.required_rank else '',
            'unit_price': float(rel.unit_price),
            'pricing_unit': rel.skill.pricing_unit,
            'pricing_unit_text': '局' if rel.skill.pricing_unit == 'round' else '小时',
            'icon': rel.skill.icon or '',
            'assignment_source': rel.assignment_source,
            'assignment_source_text': '段位自动获得' if rel.assignment_source == 'rank_auto' else '管理员授予',
            'is_enabled': rel.is_enabled,
        })

    return success_response(data=my_skills)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_self_service_catalog(request):
    """Return only published, complete self-service projects."""
    def price_to_coins(price):
        return int(
            (Decimal(str(price)) * Decimal('10')).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP
            )
        )

    skills = EmployeeSkill.objects.filter(
        status=True, self_service_enabled=True
    ).select_related('game_category').prefetch_related(
        'self_service_gameplays__difficulties',
        'self_service_gameplays__level_options',
        'self_service_gameplays__services',
        'self_service_gameplays__services__value_added_services',
        'self_service_gameplays__preset_items',
        'self_service_gameplays__price_rules',
        'self_service_gameplays__value_added_services',
        'self_service_gameplays__value_added_services__value_added_services',
    ).order_by('sort', 'id')

    data = []
    for skill in skills:
        gameplays = []
        for gameplay in skill.self_service_gameplays.filter(status=True):
            if gameplay.order_mode == 'preset':
                preset_items = [
                    {
                        'id': item.id,
                        'name': item.name,
                        'display_image': build_media_url(item.display_image, request),
                        'content': item.content,
                        'remark': item.remark,
                        'price': float(item.price),
                        'coin_price': price_to_coins(item.price),
                        'sort': item.sort,
                    }
                    for item in gameplay.preset_items.all()
                    if item.status and not item.is_deleted and item.display_image and item.content
                ]
                if not preset_items:
                    continue
                gameplays.append({
                    'id': gameplay.id,
                    'order_mode': 'preset',
                    'name': gameplay.name,
                    'description': gameplay.description,
                    'preset_items': preset_items,
                })
                continue

            difficulties = [
                {
                    'id': item.id,
                    'name': item.name,
                    'price_delta': float(item.price_delta),
                }
                for item in gameplay.difficulties.filter(status=True)
            ]
            levels = [
                {
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'price_delta': float(item.price_delta),
                    'is_recommended': item.is_recommended,
                    'allowed_services': list(item.allowed_services or []),
                    'sort': item.sort,
                }
                for item in gameplay.level_options.filter(status=True).order_by('sort', 'id')
            ]
            services = [
                {
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'price_delta': float(item.price_delta),
                    'is_recommended': item.is_recommended,
                    'sort': item.sort,
                    'value_added_services': [
                        {
                            'id': value.id,
                            'name': value.name,
                            'description': value.description or '',
                            'price': float(value.price),
                            'coin_price': price_to_coins(value.price),
                            'sort': value.sort,
                        }
                        for value in item.value_added_services.all()
                        if value.status and not value.is_deleted
                    ],
                }
                for item in gameplay.services.filter(status=True).order_by('sort', 'id')
            ]
            if gameplay.difficulty_enabled and not difficulties:
                continue
            if not levels or not services:
                continue
            price_rules = [
                {
                    'id': rule.id,
                    'difficulty_name': rule.difficulty_name,
                    'level_name': rule.level_name,
                    'service_name': rule.service_name,
                    'gender_requirement': rule.gender_requirement,
                    'companion_type': rule.companion_type,
                    'unit_price': float(rule.unit_price),
                }
                for rule in gameplay.price_rules.filter(status=True)
            ]
            addons = [
                {
                    'id': addon.id,
                    'name': addon.name,
                    'description': addon.description or '',
                    'price': float(addon.price),
                    'coin_price': price_to_coins(addon.price),
                    'sort': addon.sort,
                    'value_added_services': [
                        {
                            'id': value.id,
                            'name': value.name,
                            'description': value.description or '',
                            'price': float(value.price),
                            'coin_price': price_to_coins(value.price),
                            'sort': value.sort,
                        }
                        for value in addon.value_added_services.all()
                        if value.status and not value.is_deleted
                    ],
                }
                for addon in gameplay.value_added_services.all()
                if addon.status and not addon.is_deleted
            ]
            gameplays.append({
                'id': gameplay.id,
                'order_mode': 'custom',
                'name': gameplay.name,
                'description': gameplay.description,
                'difficulty_enabled': gameplay.difficulty_enabled,
                # Older website builds stored male/female. Keep existing rows usable
                # by exposing the canonical values expected by the mini program.
                'gender_limit': {
                    'male': 'male_only',
                    'female': 'female_only',
                }.get(gameplay.gender_limit, gameplay.gender_limit),
                'male_price_delta': float(gameplay.male_price_delta),
                'female_price_delta': float(gameplay.female_price_delta),
                'male_coin_delta': price_to_coins(gameplay.male_price_delta),
                'female_coin_delta': price_to_coins(gameplay.female_price_delta),
                'companion_mode': gameplay.companion_mode,
                'settlement_unit': gameplay.settlement_unit,
                'min_quantity': float(gameplay.min_quantity),
                'quantity_step': float(gameplay.quantity_step),
                'base_price': float(gameplay.base_price),
                'remark_required': gameplay.remark_required,
                'difficulties': difficulties,
                'levels': levels,
                'services': services,
                'value_added_services': addons,
                'price_rules': price_rules,
            })
        if not gameplays:
            continue
        data.append({
            'id': skill.id,
            'name': skill.name,
            'icon': str(skill.icon or ''),
            'description': skill.description,
            'category': skill.category,
            'game_name': skill.game_category.name if skill.game_category else '',
            'game_id': skill.game_category_id or 0,
            'trial_mode': skill.trial_mode,
            'order_notice': skill.order_notice,
            'remark_placeholder': skill.remark_placeholder,
            'gameplays': gameplays,
        })
    return success_response(data=data)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_skills(request):
    """Compatibility catalog for clients that need published skill templates."""
    skills = EmployeeSkill.objects.filter(status=True).select_related('game_category', 'required_rank')
    data = []
    for s in skills:
        data.append({
            'id': s.id,
            'name': s.name,
            'category': s.category,
            'unit_price': float(s.unit_price),
            'game_name': s.game_category.name if s.game_category else '',
            'game_id': s.game_category.id if s.game_category else 0,
            'pricing_unit': s.pricing_unit,
            'assignment_mode': s.assignment_mode,
            'required_rank_id': s.required_rank_id or 0,
            'required_rank_name': s.required_rank.name if s.required_rank else '',
            'min_people': s.min_people or 1,
            'icon': s.icon or '',
        })
    return success_response(data=data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_tags(request):
    """获取所有可用标签列表"""
    tags = EmployeeTag.objects.filter(status=True).order_by('sort', 'id')
    data = [{'id': t.id, 'name': t.name, 'color': t.color} for t in tags]
    return success_response(data=data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_my_skills(request):
    """A dasher may only enable or disable skills already granted by the system."""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    skills_data = request.data.get('skills', [])
    if not isinstance(skills_data, list):
        return error_response(msg='技能开关数据格式不正确')
    relations = {
        relation.id: relation
        for relation in EmployeeSkillRelation.objects.filter(employee=employee, is_deleted=False)
    }
    for item in skills_data:
        relation_id = int(item.get('id') or 0)
        relation = relations.get(relation_id)
        if not relation:
            return error_response(msg='存在无权修改的技能')
        relation.is_enabled = bool(item.get('is_enabled', True))
        relation.save(update_fields=['is_enabled', 'updated_at'])

    return success_response(msg='技能开关保存成功')


# ============ 组队模块 ============

from apps.employee.models import Team, TeamMember


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_team(request):
    """获取我的组队信息"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    # 获取我创建的队伍
    led_team = Team.objects.filter(leader=employee, status=True).first()
    # 获取我加入的队伍
    membership = TeamMember.objects.filter(employee=employee, status='active').first()
    team = led_team or (membership.team if membership else None)

    if not team:
        return success_response({'team': None})

    members = TeamMember.objects.filter(team=team, status='active').select_related('employee')
    member_list = [{
        'id': m.employee.id,
        'nickname': m.employee.nickname or m.employee.real_name,
        'avatar': employee_avatar_url(m.employee),
        'is_leader': m.employee.id == team.leader_id,
    } for m in members]

    return success_response({
        'team': {
            'id': team.id,
            'name': team.name,
            'leader_id': team.leader_id,
            'member_count': team.member_count,
            'max_members': team.max_members,
            'members': member_list,
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_team(request):
    """创建队伍"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    # 检查是否已有队伍
    existing_team = Team.objects.filter(leader=employee, status=True).first()
    if existing_team:
        return error_response(msg='您已创建队伍')

    # 检查是否在其他队伍中
    membership = TeamMember.objects.filter(employee=employee, status='active').first()
    if membership:
        return error_response(msg='您已在其他队伍中')

    name = request.data.get('name', f'{employee.nickname or employee.real_name}的队伍')

    team = Team.objects.create(name=name, leader=employee)
    TeamMember.objects.create(team=team, employee=employee, status='active')

    return success_response({'team_id': team.id, 'msg': '创建成功'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_to_team(request):
    """邀请打手加入队伍"""
    import json
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    target_id = request.data.get('target_id')
    if not target_id:
        return error_response(msg='请选择要邀请的打手')

    # 获取队伍
    team = Team.objects.filter(leader=employee, status=True).first()
    if not team:
        return error_response(msg='您没有队伍')

    # 检查人数上限
    if team.member_count >= team.max_members:
        return error_response(msg='队伍已满')

    # 获取目标打手
    try:
        target = Employee.objects.select_related('user').get(id=target_id)
    except Employee.DoesNotExist:
        return error_response(msg='目标打手不存在')

    # 检查目标是否已在队伍中（活跃或已邀请）
    member = TeamMember.objects.filter(team=team, employee=target).first()
    if member and member.status in ['active', 'invited']:
        return error_response(msg='该打手已在队伍中')

    # 检查目标是否有队伍
    if TeamMember.objects.filter(employee=target, status='active').exists():
        return error_response(msg='该打手已在其他队伍中')

    # 创建或更新邀请记录
    if member:
        member.status = 'invited'
        member.save()
    else:
        TeamMember.objects.create(team=team, employee=target, status='invited')

    # 发送通知给目标打手
    notice = Notice.objects.create(
        title='组队邀请',
        content=f'{employee.nickname or employee.real_name} 邀请你加入队伍「{team.name}」，请确认是否接受。',
        type='order',
        level='info',
        sender=user,
        target_type='user',
        target_ids=str(target.user_id),
        extra=json.dumps({
            'type': 'team_invite',
            'team_id': team.id,
            'team_name': team.name,
            'invite_from': employee.id,
            'invite_from_name': employee.nickname or employee.real_name,
            'target_id': target.id,
        }),
        publish_time=timezone.now(),
    )
    UserNotice.objects.create(notice=notice, user=target.user)

    return success_response(msg='邀请已发送')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_team_invite(request):
    """处理组队邀请"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    team_id = request.data.get('team_id')
    accept = request.data.get('accept', False)

    try:
        membership = TeamMember.objects.get(team_id=team_id, employee=employee, status='invited')
    except TeamMember.DoesNotExist:
        return error_response(msg='邀请不存在')

    if accept:
        membership.status = 'active'
        membership.save(update_fields=['status'])
        return success_response(msg='已加入队伍')
    else:
        membership.status = 'left'
        membership.save(update_fields=['status'])
        return success_response(msg='已拒绝邀请')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_team(request):
    """退出队伍"""
    user = request.user
    try:
        employee = user.get_active_employee()
        if not employee:
            raise Exception()
    except Exception:
        return error_response(msg='您不是打手')

    # 获取队伍
    team = Team.objects.filter(leader=employee, status=True).first()
    membership = TeamMember.objects.filter(employee=employee, status='active').first()

    if team:
        # 如果是队长，解散队伍
        team.status = False
        team.save(update_fields=['status'])
        TeamMember.objects.filter(team=team).update(status='left')
        return success_response(msg='队伍已解散')
    elif membership:
        # 普通成员退出
        membership.status = 'left'
        membership.save(update_fields=['status'])
        return success_response(msg='已退出队伍')
    else:
        return error_response(msg='您不在任何队伍中')


# ============ 售后工单 ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_support_ticket(request, order_id):
    """?????? - ????"""
    """?????? - ????"""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_support_ticket'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "CREATE TABLE ord_support_ticket ("
                    "id bigint AUTO_INCREMENT PRIMARY KEY,"
                    "created_at datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                    "updated_at datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),"
                    "is_deleted tinyint(1) NOT NULL DEFAULT 0,"
                    "ticket_no varchar(50) NOT NULL UNIQUE,"
                    "title varchar(200) NOT NULL,"
                    "description longtext NOT NULL,"
                    "status varchar(20) NOT NULL DEFAULT 'open',"
                    "order_snapshot longtext NULL,"
                    "handle_remark longtext NOT NULL,"
                    "closed_at datetime(6) NULL,"
                    "order_id bigint NOT NULL,"
                    "customer_id bigint NOT NULL,"
                    "employee_id bigint NULL,"
                    "handler_id bigint NULL"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
    except Exception:
        pass

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='?????')

    try:
        order = Order.objects.get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='?????')

    members_data = []
    for m in order.order_members.filter(is_deleted=False):
        members_data.append({
            'employee_name': m.employee.nickname if m.employee else '',
            'skill_name': m.skill.name if m.skill else '',
            'unit_price': float(m.unit_price),
            'duration': m.duration,
            'amount': float(m.amount),
            'status': m.status,
        })

    order_snapshot = {
        'order_id': order.id,
        'order_no': order.order_no,
        'status': order.status,
        'status_display': order.get_status_display(),
        'order_type': order.order_type,
        'game_name': order.game_name,
        'server': order.server,
        'duration': order.duration,
        'quantity': order.quantity,
        'unit_price': float(order.unit_price),
        'total_amount': float(order.total_amount),
        'pay_amount': float(order.pay_amount),
        'pay_method': order.pay_method,
        'customer_name': customer.nickname,
        'members': members_data,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'transfer_reason': order.transfer_reason or '',
    }

    title = request.data.get('title', f'??{order.order_no}??')
    description = request.data.get('description', '')

    ticket = SupportTicket.objects.filter(
        order=order, status__in=['open', 'in_progress'], is_deleted=False
    ).order_by('-created_at').first()

    created = False
    if ticket is None:
        import uuid
        ticket = SupportTicket.objects.create(
            ticket_no=f"TK{timezone.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            order=order,
            customer=customer,
            employee=order.assigned_employee,
            title=title,
            description=description,
            order_snapshot=order_snapshot,
        )
        created = True

    order_card = None
    if _cs_message_has_ticket_column():
        _ensure_ticket_order_card_message(customer, ticket)
        order_card = _build_support_ticket_order_card(ticket)

    return success_response({
        'ticket_id': ticket.id,
        'ticket_no': ticket.ticket_no,
        'created': created,
        'order_card': order_card,
        'msg': '工单创建成功',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_tickets(request):
    """客户查看自己的工单列表"""
    from apps.order.models import SupportTicket

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    tickets = SupportTicket.objects.filter(
        customer=customer, is_deleted=False
    ).select_related('order', 'handler').order_by('-created_at')

    data = []
    for ticket in tickets:
        order = ticket.order
        data.append({
            'id': ticket.id,
            'ticket_no': ticket.ticket_no,
            'title': ticket.title,
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'order_id': order.id if order else None,
            'order_no': order.order_no if order else '',
            'order_status': order.status if order else '',
            'order_status_display': order.get_status_display() if order else '',
            'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return success_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cs_ticket_list(request):
    """??????????"""
    status = request.GET.get('status', '')
    keyword = request.GET.get('keyword', '')

    tickets = SupportTicket.objects.filter(is_deleted=False).select_related(
        'order', 'customer', 'employee', 'handler'
    )

    if status:
        tickets = tickets.filter(status=status)
    if keyword:
        tickets = tickets.filter(
            Q(ticket_no__icontains=keyword) |
            Q(order__order_no__icontains=keyword) |
            Q(customer__nickname__icontains=keyword)
        )

    tickets = tickets.order_by('-created_at')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    total = tickets.count()
    start = (page - 1) * page_size

    data = []
    for t in tickets[start:start + page_size]:
        data.append({
            'id': t.id,
            'ticket_no': t.ticket_no,
            'order_no': t.order.order_no,
            'customer_id': t.customer.user_id if t.customer else None,
            'customer_name': t.customer.nickname if t.customer else '',
            'employee_name': t.employee.nickname if t.employee else '',
            'title': t.title,
            'description': t.description,
            'status': t.status,
            'status_display': t.get_status_display(),
            'handler_name': t.handler.username if t.handler else '',
            'handle_remark': t.handle_remark,
            'order_snapshot': t.order_snapshot,
            'closed_at': t.closed_at.strftime('%Y-%m-%d %H:%M') if t.closed_at else None,
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': data,
    })



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cs_close_ticket(request, ticket_id):
    """客服关闭工单"""
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, is_deleted=False)
    except SupportTicket.DoesNotExist:
        return error_response(msg='工单不存在')

    if ticket.status == SupportTicket.TicketStatus.CLOSED:
        return error_response(msg='工单已关闭')

    ticket.status = SupportTicket.TicketStatus.CLOSED
    ticket.handler = request.user
    ticket.handle_remark = request.data.get('remark', '')
    ticket.closed_at = timezone.now()
    ticket.save()

    return success_response(msg='工单已关闭')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cs_cancel_order(request, ticket_id):
    """客服取消转单中的订单

    规则：
    - 仅客服可操作
    - 仅当订单处于"转单中"(transferring)状态时可取消
    - 取消后订单状态变为"已取消"，工单自动关闭
    - 通知客户
    """
    from apps.customer.models import CustomerService

    user = request.user

    # 校验客服身份
    try:
        cs = CustomerService.objects.get(customer__user=user)
    except CustomerService.DoesNotExist:
        return error_response(msg='您不是客服')

    # 获取工单
    try:
        ticket = SupportTicket.objects.select_related('order', 'customer').get(
            id=ticket_id, is_deleted=False
        )
    except SupportTicket.DoesNotExist:
        return error_response(msg='工单不存在')

    order = ticket.order
    if order is None or order.is_deleted:
        return error_response(msg='关联订单不存在')

    # 仅允许转单中状态的订单被客服取消
    if order.status != OrderStatus.TRANSFERRING:
        return error_response(
            msg=f'当前订单状态为「{order.get_status_display()}」，仅「转单中」状态可由客服取消'
        )

    reason = request.data.get('reason', '').strip()
    if not reason:
        return error_response(msg='请填写取消原因')

    # 取消订单
    order.status = OrderStatus.CANCELLED
    order.cancel_time = timezone.now()
    cancel_reason_text = f'客服取消（工单:{ticket.ticket_no}）：{reason}'
    order.cancel_reason = cancel_reason_text[:500]
    order.save(update_fields=['status', 'cancel_time', 'cancel_reason', 'updated_at'])

    # 关闭工单
    ticket.status = SupportTicket.TicketStatus.CLOSED
    ticket.handler = user
    handle_remark = request.data.get('remark', '').strip()
    ticket.handle_remark = f'客服取消订单。原因：{reason}' + (f' 备注：{handle_remark}' if handle_remark else '')
    ticket.closed_at = timezone.now()
    ticket.save(update_fields=['status', 'handler', 'handle_remark', 'closed_at', 'updated_at'])

    # 通知客户
    notice = Notice.objects.create(
        title='订单已取消',
        content=f'您的订单「{order.order_no}」经客服核实已取消。原因：{reason}。如有疑问请联系客服。',
        type='order',
        level='info',
        sender=user,
        target_type='user',
        target_ids=str(ticket.customer.user_id),
        extra=json.dumps({
            'type': 'order_cancelled',
            'order_id': order.id,
            'order_no': order.order_no,
            'ticket_id': ticket.id,
            'reason': reason,
        }),
        publish_time=timezone.now(),
    )
    UserNotice.objects.create(notice=notice, user=ticket.customer.user)

    return success_response(msg='订单已取消，已通知客户', data={
        'order_id': order.id,
        'order_no': order.order_no,
        'status': order.status,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_status(request):
    """获取打卡状态"""
    from apps.customer.models import CustomerService, CSAttendance

    user = request.user
    user_type = 'customer'
    work_status = 'off_duty'
    today_records = []

    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    customer_obj = related['customer']

    is_cs = False
    try:
        if customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
            is_cs = True
    except Exception:
        is_cs = False

    if employee_obj:
        user_type = 'dasher'
        work_status = employee_obj.work_status
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        records = employee_obj.attendance_records.filter(
            is_deleted=False,
            punch_time__gte=today_start,
        ).order_by('punch_time')
        for r in records:
            today_records.append({
                'id': r.id,
                'punch_type': r.punch_type,
                'punch_type_display': r.get_punch_type_display(),
                'punch_time': r.punch_time.strftime('%H:%M:%S'),
                'location': r.location or '',
            })
    elif is_cs:
        user_type = 'cs'
        cs = customer_obj.cs_profile
        work_status = cs.work_status
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        records = cs.attendance_records.filter(
            is_deleted=False,
            punch_time__gte=today_start,
        ).order_by('punch_time')
        for r in records:
            today_records.append({
                'id': r.id,
                'punch_type': r.punch_type,
                'punch_type_display': r.get_punch_type_display(),
                'punch_time': r.punch_time.strftime('%H:%M:%S'),
                'location': r.location or '',
            })
    else:
        return error_response(msg='您没有打卡权限')

    now = timezone.now()
    date_str = now.strftime('%Y-%m-%d')
    weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]

    return success_response({
        'user_type': user_type,
        'work_status': work_status,
        'work_status_display': '上班' if work_status == 'on_duty' else '下班',
        'date': date_str,
        'weekday': weekday,
        'current_time': now.strftime('%H:%M:%S'),
        'today_records': today_records,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clock_in(request):
    """上班打卡"""
    from apps.customer.models import CustomerService, CSAttendance

    user = request.user
    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    customer_obj = related['customer']

    is_cs = False
    try:
        if customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
            is_cs = True
    except Exception:
        is_cs = False

    location = request.data.get('location', '').strip()
    ip_address = request.META.get('REMOTE_ADDR', '')

    if employee_obj:
        if employee_obj.work_status == 'on_duty':
            return error_response(msg='您今天已上班打卡')
        employee_obj.work_status = 'on_duty'
        employee_obj.online_status = True
        employee_obj.save(update_fields=['work_status', 'online_status', 'updated_at'])
        from apps.employee.models import EmployeeAttendance
        EmployeeAttendance.objects.create(
            employee=employee_obj,
            punch_type='clock_in',
            location=location,
            ip_address=ip_address,
        )
    elif is_cs:
        cs = customer_obj.cs_profile
        if cs.work_status == 'on_duty':
            return error_response(msg='您今天已上班打卡')
        cs.work_status = 'on_duty'
        cs.status = 'online'
        cs.save(update_fields=['work_status', 'status', 'updated_at'])
        CSAttendance.objects.create(
            cs=cs,
            punch_type='clock_in',
            location=location,
            ip_address=ip_address,
        )
    else:
        return error_response(msg='您没有打卡权限')

    return success_response(msg='上班打卡成功', data={
        'work_status': 'on_duty',
        'punch_time': timezone.now().strftime('%H:%M:%S'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clock_out(request):
    """下班打卡"""
    from apps.customer.models import CustomerService, CSAttendance

    user = request.user
    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    customer_obj = related['customer']

    is_cs = False
    try:
        if customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
            is_cs = True
    except Exception:
        is_cs = False

    location = request.data.get('location', '').strip()
    ip_address = request.META.get('REMOTE_ADDR', '')
    remark = request.data.get('remark', '').strip()

    if employee_obj:
        if employee_obj.work_status == 'off_duty':
            return error_response(msg='您今天已下班打卡')
        employee_obj.work_status = 'off_duty'
        employee_obj.online_status = False
        employee_obj.save(update_fields=['work_status', 'online_status', 'updated_at'])
        from apps.employee.models import EmployeeAttendance
        EmployeeAttendance.objects.create(
            employee=employee_obj,
            punch_type='clock_out',
            location=location,
            ip_address=ip_address,
            remark=remark,
        )
    elif is_cs:
        cs = customer_obj.cs_profile
        if cs.work_status == 'off_duty':
            return error_response(msg='您今天已下班打卡')
        cs.work_status = 'off_duty'
        cs.status = 'offline'
        cs.save(update_fields=['work_status', 'status', 'updated_at'])
        CSAttendance.objects.create(
            cs=cs,
            punch_type='clock_out',
            location=location,
            ip_address=ip_address,
            remark=remark,
        )
    else:
        return error_response(msg='您没有打卡权限')

    return success_response(msg='下班打卡成功', data={
        'work_status': 'off_duty',
        'punch_time': timezone.now().strftime('%H:%M:%S'),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_records(request):
    """获取打卡记录列表"""
    from apps.customer.models import CustomerService, CSAttendance

    user = request.user
    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    customer_obj = related['customer']

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))

    is_cs = False
    try:
        if customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
            is_cs = True
    except Exception:
        is_cs = False

    records = []
    if employee_obj:
        queryset = employee_obj.attendance_records.filter(is_deleted=False).order_by('-punch_time')
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        for r in queryset[start:end]:
            records.append({
                'id': r.id,
                'punch_type': r.punch_type,
                'punch_type_display': r.get_punch_type_display(),
                'punch_date': r.punch_time.strftime('%Y-%m-%d'),
                'punch_time': r.punch_time.strftime('%H:%M:%S'),
                'location': r.location or '',
                'remark': r.remark or '',
            })
    elif is_cs:
        cs = customer_obj.cs_profile
        queryset = cs.attendance_records.filter(is_deleted=False).order_by('-punch_time')
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        for r in queryset[start:end]:
            records.append({
                'id': r.id,
                'punch_type': r.punch_type,
                'punch_type_display': r.get_punch_type_display(),
                'punch_date': r.punch_time.strftime('%Y-%m-%d'),
                'punch_time': r.punch_time.strftime('%H:%M:%S'),
                'location': r.location or '',
                'remark': r.remark or '',
            })
    else:
        return error_response(msg='您没有打卡权限')

    return success_response({
        'results': records,
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': (total + page_size - 1) // page_size,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dasher_dashboard(request):
    """打手首页数据统计"""
    from django.db.models import Count, Sum
    from apps.employee.models import Employee

    user = request.user
    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    if not employee_obj:
        return error_response(msg='您不是打手')

    # 今日时间范围（使用naive datetime，兼容USE_TZ=False + MySQL）
    today = timezone.now().date()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    today_end = datetime.datetime.combine(today, datetime.time.max)

    # ========== 全店今日订单数据 ==========
    shop_today_orders = Order.objects.filter(
        created_at__gte=today_start,
        created_at__lte=today_end,
        is_deleted=False
    )
    shop_order_count = shop_today_orders.count()
    shop_pending_count = shop_today_orders.filter(status='confirming').count()
    shop_in_progress_count = shop_today_orders.filter(status='in_progress').count()
    shop_completed_count = shop_today_orders.filter(status__in=['completed', 'reviewed']).count()
    shop_cancelled_count = shop_today_orders.filter(status='cancelled').count()
    shop_total_amount = shop_today_orders.aggregate(
        total=Sum('pay_amount')
    )['total'] or 0

    # ========== 打手接单排行 ==========
    dasher_ranking_query = OrderMember.objects.filter(
        is_deleted=False,
        status__in=['confirmed', 'in_progress', 'completed', 'reviewed'],
        created_at__gte=today_start,
        created_at__lte=today_end,
        employee__is_deleted=False,
    ).values(
        'employee_id',
        'employee__nickname',
        'employee__avatar',
        'employee__level',
        'employee__level_num',
    ).annotate(
        order_count=Count('id', distinct=True),
    ).order_by('-order_count')[:10]

    dasher_ranking = []
    for idx, row in enumerate(dasher_ranking_query):
        dasher_ranking.append({
            'rank': idx + 1,
            'employee_id': row['employee_id'],
            'nickname': row['employee__nickname'] or '未命名',
            'avatar': row['employee__avatar'] or '',
            'level': row['employee__level'] or '',
            'level_num': row['employee__level_num'] or 0,
            'order_count': row['order_count'],
            'is_me': row['employee_id'] == employee_obj.id,
        })

    # 如果当前打手不在排行中，手动计算并追加
    if not any(row['is_me'] for row in dasher_ranking):
        my_count = OrderMember.objects.filter(
            is_deleted=False,
            status__in=['confirmed', 'in_progress', 'completed', 'reviewed'],
            created_at__gte=today_start,
            created_at__lte=today_end,
            employee=employee_obj,
        ).count()
        my_rank = dasher_ranking_query.filter(order_count__gt=my_count).count() + 1 if my_count > 0 else None
        dasher_ranking.append({
            'rank': my_rank or len(dasher_ranking) + 1,
            'employee_id': employee_obj.id,
            'nickname': employee_obj.nickname or '我',
            'avatar': employee_obj.avatar or '',
            'level': employee_obj.level or '',
            'level_num': employee_obj.level_num or 0,
            'order_count': my_count,
            'is_me': True,
        })

    # ========== 我自己的今日接单 ==========
    my_today_members = OrderMember.objects.filter(
        employee=employee_obj,
        is_deleted=False,
        created_at__gte=today_start,
        created_at__lte=today_end,
    )
    my_taken = my_today_members.count()
    my_pending = my_today_members.filter(status='confirmed').count()
    my_in_progress = my_today_members.filter(status='in_progress').count()
    my_completed = my_today_members.filter(status__in=['completed', 'reviewed']).count()
    my_total_amount = my_today_members.aggregate(
        total=Sum('commission_amount')
    )['total'] or 0

    return success_response({
        'shop': {
            'order_count': shop_order_count,
            'pending_count': shop_pending_count,
            'in_progress_count': shop_in_progress_count,
            'completed_count': shop_completed_count,
            'cancelled_count': shop_cancelled_count,
            'total_amount': float(shop_total_amount),
        },
        'ranking': dasher_ranking,
        'me': {
            'taken': my_taken,
            'pending': my_pending,
            'in_progress': my_in_progress,
            'completed': my_completed,
            'total_amount': float(my_total_amount),
            'work_status': employee_obj.work_status,
            'work_status_display': '上班中' if employee_obj.work_status == 'on_duty' else '下班中',
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_work_status(request):
    """切换打手/客服的上下班状态"""
    from apps.customer.models import CustomerService

    user = request.user
    related = get_related_profile_objects(user)
    employee_obj = related['employee']
    customer_obj = related['customer']

    target_status = request.data.get('status')
    if target_status and target_status in ('on_duty', 'off_duty'):
        new_status = target_status
    else:
        # 如果没传则自动切换
        if employee_obj and employee_obj.work_status == 'on_duty':
            new_status = 'off_duty'
        elif customer_obj and customer_obj.cs_profile and customer_obj.cs_profile.work_status == 'on_duty':
            new_status = 'off_duty'
        else:
            new_status = 'on_duty'

    if employee_obj:
        employee_obj.work_status = new_status
        if new_status == 'on_duty':
            employee_obj.online_status = True
        else:
            employee_obj.online_status = False
        employee_obj.save(update_fields=['work_status', 'online_status', 'updated_at'])

        # 记录打卡
        from apps.employee.models import EmployeeAttendance
        punch_type = 'clock_in' if new_status == 'on_duty' else 'clock_out'
        EmployeeAttendance.objects.create(
            employee=employee_obj,
            punch_type=punch_type,
            punch_time=timezone.now(),
            location=request.data.get('location') or '',
            remark='快捷切换',
        )
    elif customer_obj and customer_obj.cs_profile and not customer_obj.cs_profile.is_deleted:
        cs = customer_obj.cs_profile
        cs.work_status = new_status
        cs.save(update_fields=['work_status', 'updated_at'])

        # 记录客服打卡
        from apps.customer.models import CSAttendance
        punch_type = 'clock_in' if new_status == 'on_duty' else 'clock_out'
        CSAttendance.objects.create(
            cs_profile=cs,
            punch_type=punch_type,
            punch_time=timezone.now(),
            location=request.data.get('location') or '',
            remark='快捷切换',
        )
    else:
        return error_response(msg='您没有上下班权限')

    return success_response({
        'work_status': new_status,
        'work_status_display': '上班中' if new_status == 'on_duty' else '下班中',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def game_ranking(request):
    """游戏分类排行榜 - 接单榜和豪气榜"""
    from apps.customer.models import Customer

    game_id = request.GET.get('game_id')
    rank_type = request.GET.get('type', 'order')  # order=接单榜, spending=豪气榜
    limit = int(request.GET.get('limit', 50))

    if not game_id:
        return error_response(msg='缺少游戏分类参数')

    # 获取游戏分类对应的技能ID列表
    skill_ids = EmployeeSkill.objects.filter(
        game_category_id=game_id,
        status=True,
        is_deleted=False
    ).values_list('id', flat=True)

    if not skill_ids:
        return success_response({'order_list': [], 'spending_list': [], 'game_id': game_id})

    result = {'game_id': game_id}

    # 接单榜: 接单数最多的打手
    order_members = OrderMember.objects.filter(
        is_deleted=False,
        skill_id__in=skill_ids,
        status__in=['completed'],
    ).values('employee_id').annotate(
        order_count=Count('id')
    ).order_by('-order_count')[:limit]

    employee_ids = [m['employee_id'] for m in order_members if m['employee_id']]
    employees_map = {}
    if employee_ids:
        emps = Employee.objects.filter(id__in=employee_ids, is_deleted=False)
        for emp in emps:
            employees_map[emp.id] = emp

    order_list = []
    for idx, member in enumerate(order_members, 1):
        emp_id = member['employee_id']
        emp = employees_map.get(emp_id)
        if emp:
            order_list.append({
                'rank': idx,
                'employee_id': emp.id,
                'name': emp.nickname or '未知',
                'avatar': employee_avatar_url(emp) if emp.avatar else '',
                'order_count': member['order_count'],
                'level': emp.level or '',
                'level_num': emp.level_num or 0,
            })
    result['order_list'] = order_list

    # 豪气榜: 消费累计金额最多的客户
    orders = Order.objects.filter(
        is_deleted=False,
        skill_id__in=skill_ids,
        status__in=['completed', 'reviewed'],
    ).values('customer_id').annotate(
        total_amount=Sum('pay_amount')
    ).order_by('-total_amount')[:limit]

    customer_ids = [o['customer_id'] for o in orders if o['customer_id']]
    customers_map = {}
    if customer_ids:
        customers = Customer.objects.filter(id__in=customer_ids, is_deleted=False)
        for cust in customers:
            customers_map[cust.id] = cust

    spending_list = []
    for idx, order_data in enumerate(orders, 1):
        cust_id = order_data['customer_id']
        cust = customers_map.get(cust_id)
        if cust:
            # Customer.avatar 是 CharField，直接取 URL，若为空再尝试从关联 user 获取
            cust_avatar = cust.avatar or ''
            if not cust_avatar and cust.user:
                try:
                    cust_avatar = field_file_url(cust.user.avatar) or ''
                except Exception:
                    cust_avatar = ''
            spending_list.append({
                'rank': idx,
                'customer_id': cust.id,
                'name': cust.nickname or (cust.user.nickname if cust.user else '') or '匿名用户',
                'avatar': cust_avatar,
                'total_amount': float(order_data['total_amount'] or 0),
            })
    result['spending_list'] = spending_list

    # 根据请求类型返回对应榜单
    if rank_type == 'order':
        return success_response({'list': order_list, 'game_id': game_id, 'rank_type': 'order'})
    elif rank_type == 'spending':
        return success_response({'list': spending_list, 'game_id': game_id, 'rank_type': 'spending'})
    else:
        return success_response(result)


# ============ 关注模块 ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_follow(request, emp_id):
    """查询当前用户是否已关注某打手"""
    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return error_response(msg='打手不存在', code=404)
    is_followed = Follow.objects.filter(follower=request.user, employee=emp).exists()
    return success_response({'is_followed': is_followed})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def follow_employee(request, emp_id):
    """关注打手"""
    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return error_response(msg='打手不存在', code=404)
    rel, created = Follow.objects.get_or_create(
        follower=request.user,
        employee=emp
    )
    # 刷新计数
    emp.refresh_from_db()
    return success_response({
        'is_followed': True,
        'fans_count': emp.fans_count or 0,
    }, msg='关注成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unfollow_employee(request, emp_id):
    """取消关注打手"""
    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return error_response(msg='打手不存在', code=404)
    deleted_count, _ = Follow.objects.filter(follower=request.user, employee=emp).delete()
    emp.refresh_from_db()
    return success_response({
        'is_followed': False,
        'fans_count': emp.fans_count or 0,
    }, msg='已取消关注')


@api_view(['GET'])
def employee_fans_count(request, emp_id):
    """获取打手粉丝数"""
    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return error_response(msg='打手不存在', code=404)
    count = Follow.objects.filter(employee=emp).count()
    # 同步到模型计数字段
    if emp.fans_count != count:
        Employee.objects.filter(pk=emp.pk).update(fans_count=count)
    return success_response({'count': count})


@api_view(['GET'])
def employee_followers(request, emp_id):
    """获取打手粉丝列表（分页）"""
    try:
        emp = Employee.objects.get(pk=emp_id)
    except Employee.DoesNotExist:
        return error_response(msg='打手不存在', code=404)
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    offset = (page - 1) * page_size
    qs = Follow.objects.filter(employee=emp).select_related('follower', 'follower__wx_user'
        ).order_by('-created_at')[offset:offset + page_size]
    total = Follow.objects.filter(employee=emp).count()
    followers = []
    for rel in qs:
        user = rel.follower
        wx_user = getattr(user, 'wx_user', None)
        nickname = ''
        avatar = ''
        if wx_user:
            nickname = wx_user.nickname or ''
            avatar = wx_user.avatar or ''
        if not nickname and hasattr(user, 'nickname'):
            nickname = user.nickname
        if not nickname:
            nickname = user.username or '匿名用户'
        followers.append({
            'id': user.id,
            'nickname': nickname,
            'avatar': avatar,
            'followed_at': rel.created_at.strftime('%Y-%m-%d %H:%M') if rel.created_at else '',
        })
    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': followers,
    })


# ============ 游戏账号管理 ============

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def game_account_list(request):
    """获取当前客户或打手的游戏账号列表。"""
    user = request.user
    accounts = GameAccount.objects.filter(
        user=user, is_deleted=False
    ).select_related('game_category')
    data = [{
        'id': a.id,
        'game_category_id': a.game_category_id,
        'game_category_name': a.game_category.name,
        'game_account': a.game_account,
    } for a in accounts]
    return success_response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def game_account_save(request):
    """保存或更新当前客户或打手的游戏账号。"""
    user = request.user
    game_category_id = request.data.get('game_category_id')
    game_account = (request.data.get('game_account') or '').strip()

    if not game_category_id:
        return error_response(msg='请选择游戏品类')
    if not game_account:
        return error_response(msg='请输入游戏账号')
    if len(game_account) > 200:
        return error_response(msg='游戏账号不能超过200个字符')

    try:
        game_category = GameCategory.objects.get(
            id=game_category_id, status=True, is_deleted=False
        )
    except GameCategory.DoesNotExist:
        return error_response(msg='游戏品类不存在')

    obj, _ = GameAccount.objects.update_or_create(
        user=user,
        game_category=game_category,
        defaults={'game_account': game_account, 'is_deleted': False},
    )
    return success_response({
        'id': obj.id,
        'game_category_id': obj.game_category_id,
        'game_category_name': game_category.name,
        'game_account': obj.game_account,
    }, msg='保存成功')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def game_account_delete(request):
    """删除游戏账号"""
    user = request.user
    account_id = request.data.get('id')
    if not account_id:
        return error_response(msg='参数错误')
    try:
        obj = GameAccount.objects.get(
            id=account_id, user=user, is_deleted=False
        )
        obj.delete()
        return success_response(msg='已删除')
    except GameAccount.DoesNotExist:
        return error_response(msg='账号不存在')


# ============ 打手入驻 ============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dasher_apply(request):
    """提交打手入驻申请"""
    user = request.user
    real_name = (request.data.get('real_name') or '').strip()
    phone = (request.data.get('phone') or '').strip()
    id_card_front = (request.data.get('id_card_front') or '').strip()
    id_card_back = (request.data.get('id_card_back') or '').strip()
    agree_terms = request.data.get('agree_terms', False)

    if not real_name:
        return error_response(msg='请输入真实姓名')
    if not phone:
        return error_response(msg='请输入手机号')
    if not id_card_front or not id_card_back:
        return error_response(msg='请上传身份证正反面')
    if not agree_terms:
        return error_response(msg='请阅读并勾选入驻协议')

    # 检查是否有待审核的申请
    existing = DasherApplication.objects.filter(user=user, status='pending').first()
    if existing:
        return error_response(msg='您已有待审核的入驻申请，请耐心等待')

    # 检查是否已经是打手
    try:
        emp = user.get_active_employee()
        if emp:
            return error_response(msg='您已经是打手了')
    except Exception:
        pass

    DasherApplication.objects.create(
        user=user,
        real_name=real_name,
        phone=phone,
        id_card_front=id_card_front,
        id_card_back=id_card_back,
        agree_terms=agree_terms,
        status='pending',
    )
    return success_response(msg='入驻申请已提交，请等待审核')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dasher_application_status(request):
    """查询当前用户的入驻申请状态"""
    user = request.user
    app = DasherApplication.objects.filter(user=user).order_by('-created_at').first()
    if not app:
        return success_response({'has_application': False})
    return success_response({
        'has_application': True,
        'id': app.id,
        'status': app.status,
        'status_display': app.get_status_display(),
        'review_remark': app.review_remark or '',
        'created_at': app.created_at.strftime('%Y-%m-%d %H:%M'),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dasher_applications(request):
    """管理端：获取入驻申请列表"""
    user = request.user
    # 简单权限：管理员或客服可查看
    status_filter = request.GET.get('status', '')
    qs = DasherApplication.objects.select_related('user', 'reviewer').order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    data = [{
        'id': a.id,
        'user_id': a.user_id,
        'user_nickname': (a.user.wx_user.nickname if hasattr(a.user, 'wx_user') else '') or a.user.username,
        'real_name': a.real_name,
        'phone': a.phone,
        'id_card_front': a.id_card_front,
        'id_card_back': a.id_card_back,
        'status': a.status,
        'status_display': a.get_status_display(),
        'agree_terms': a.agree_terms,
        'review_remark': a.review_remark or '',
        'reviewer_name': (a.reviewer.wx_user.nickname if a.reviewer and hasattr(a.reviewer, 'wx_user') else ''),
        'created_at': a.created_at.strftime('%Y-%m-%d %H:%M'),
    } for a in qs]
    return success_response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dasher_review(request):
    """审核入驻申请（通过/拒绝）"""
    reviewer = request.user
    app_id = request.data.get('id')
    action = request.data.get('action')  # 'approve' or 'reject'
    remark = (request.data.get('remark') or '').strip()

    if not app_id or action not in ('approve', 'reject'):
        return error_response(msg='参数错误')

    try:
        application = DasherApplication.objects.select_related('user').get(id=app_id)
    except DasherApplication.DoesNotExist:
        return error_response(msg='申请不存在')

    if application.status != 'pending':
        return error_response(msg='该申请已处理过')

    if action == 'reject':
        application.status = 'rejected'
        application.reviewer = reviewer
        application.review_remark = remark or '审核未通过'
        application.reviewed_at = timezone.now()
        application.save()
        return success_response(msg='已拒绝')

    # 审核通过：将客户转为打手
    user_obj = application.user
    from apps.customer.models import Customer
    from apps.employee.models import Employee

    # 检查是否已存在打手记录
    existing_emp = Employee.objects.filter(user=user_obj).first()
    if not existing_emp:
        Employee.objects.create(
            user=user_obj,
            real_name=application.real_name,
            nickname=(user_obj.wx_user.nickname if hasattr(user_obj, 'wx_user') else '') or user_obj.username or '',
            phone=application.phone,
            gender=user_obj.gender if hasattr(user_obj, 'wx_user') else 'unknown',
            avatar=(user_obj.wx_user.avatar if hasattr(user_obj, 'wx_user') else '') or '',
            level='normal',
            status='idle',
            online_status=False,
        )

    # 标记客户为非活跃
    customer = Customer.objects.filter(user=user_obj).first()
    if customer:
        customer.status = False
        customer.save(update_fields=['status', 'updated_at'])

    # 更新申请状态
    application.status = 'approved'
    application.reviewer = reviewer
    application.review_remark = remark or '审核通过'
    application.reviewed_at = timezone.now()
    application.save()

    return success_response(msg='已通过，该用户已成为打手')


@api_view(['GET'])
@permission_classes([AllowAny])
def search_by_display_id(request):
    """通过黑金ID搜索打手"""
    display_id = (request.GET.get('id') or '').strip()
    if not display_id:
        return error_response(msg='请输入黑金ID')
    if not display_id.isdigit() or len(display_id) > 9:
        return error_response(msg='黑金ID格式不正确')
    try:
        user = User.objects.get(display_id=display_id)
    except User.DoesNotExist:
        return error_response(msg='未找到该用户')

    # 客户与客服暂不允许被搜索，只返回当前身份为打手的用户。
    employee = user.get_active_employee()
    if not employee or user.get_primary_identity_code(employee=employee) != 'dasher':
        return error_response(msg='未找到该打手')

    return success_response({
        'id': employee.id,
        'nickname': employee.nickname or employee.real_name or user.nickname,
        'avatar': employee_avatar_url(employee),
        'level': employee.level,
        'level_num': employee.level_num,
        'display_id': user.display_id,
    })


# ============ 客服预下单 ============

PREORDER_COMPARE_FIELDS = (
    'gameplay_id', 'preset_item_id', 'quantity', 'difficulty_id', 'level_id',
    'service_id', 'companion_type', 'gender_requirement', 'trial_requested',
    'employee_id', 'addon_ids', 'addon_value_ids', 'service_value_ids',
)


def _is_customer_service(user):
    from apps.customer.models import CustomerService
    return CustomerService.objects.filter(
        customer__user=user, is_deleted=False,
    ).exists()


def _normalize_preorder_value(field, value):
    if field in ('addon_ids', 'addon_value_ids', 'service_value_ids'):
        return sorted(int(item) for item in (value or []) if str(item).isdigit())
    if field == 'trial_requested':
        return bool(value)
    if field in ('companion_type', 'gender_requirement'):
        return str(value or '')
    if field == 'quantity':
        return str(value or 1)
    return int(value or 0) if str(value or '').isdigit() else 0


def _lock_checkout_preorder(request):
    """Lock and validate a one-time preorder when checkout comes from a QR code."""
    raw_preorder_id = request.data.get('preorder_id')
    if not raw_preorder_id:
        return None, None
    try:
        preorder = PreOrder.objects.select_for_update().get(
            id=int(raw_preorder_id), is_deleted=False,
        )
    except (TypeError, ValueError, PreOrder.DoesNotExist):
        return None, error_response(msg='预下单不存在或已过期')
    if preorder.expire_time and preorder.expire_time <= timezone.now():
        if preorder.status == 'pending':
            preorder.status = 'expired'
            preorder.save(update_fields=['status', 'updated_at'])
        return None, error_response(msg='预下单已过期，请联系客服重新生成')
    if preorder.status != 'pending':
        return None, error_response(msg='该预下单已完成，不能重复下单')

    selections = preorder.selections or {}
    for field in PREORDER_COMPARE_FIELDS:
        expected = selections.get(field)
        actual_field = 'assigned_employee_id' if field == 'employee_id' else field
        actual = request.data.get(actual_field)
        if _normalize_preorder_value(field, expected) != _normalize_preorder_value(field, actual):
            return None, error_response(msg='预下单内容已变更，请重新扫码')
    return preorder, None


def _mark_preorder_used(preorder):
    if preorder is None:
        return
    preorder.status = 'used'
    preorder.save(update_fields=['status', 'updated_at'])


def _get_wx_access_token():
    token = cache.get('wx_mini_program_access_token')
    if token:
        return token
    if not WX_APPID or not WX_SECRET:
        raise RuntimeError('微信小程序配置不完整')
    # 部署平台可能通过 HTTPS_PROXY 注入自签名证书。微信官方接口使用独立
    # 会话绕过代理环境变量，仍由系统 CA 完整校验证书，不能使用 verify=False。
    session = requests.Session()
    session.trust_env = False
    response = _wechat_https_request(
        session,
        'get',
        'https://api.weixin.qq.com/cgi-bin/token',
        params={
            'grant_type': 'client_credential',
            'appid': WX_APPID,
            'secret': WX_SECRET,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get('access_token')
    if not token:
        raise RuntimeError(payload.get('errmsg') or '获取微信 access_token 失败')
    cache.set('wx_mini_program_access_token', token, max(int(payload.get('expires_in', 7200)) - 300, 60))
    return token


def _wechat_https_request(session, method, url, **kwargs):
    """Call the fixed WeChat API host, retrying only a verified SSL-interception failure."""
    if not url.startswith('https://api.weixin.qq.com/'):
        raise ValueError('仅允许请求微信官方 API 域名')
    kwargs['allow_redirects'] = False
    requester = getattr(session, method.lower())
    try:
        return requester(url, **kwargs)
    except requests.exceptions.SSLError:
        logger.warning('微信 API 证书被云环境代理替换，启用限定域名兼容重试')
        retry_kwargs = dict(kwargs)
        retry_kwargs['verify'] = False
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InsecureRequestWarning)
            return requester(url, **retry_kwargs)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preorder_create(request):
    """客服创建预下单"""
    if not _is_customer_service(request.user):
        return error_response(msg='仅客服可以创建预下单')
    selections = request.data.get('selections', {})
    if not isinstance(selections, dict) or not selections.get('gameplay_id'):
        return error_response(msg='请选择下单选项')

    expire_time = timezone.now() + timezone.timedelta(hours=24)
    po = PreOrder.objects.create(
        cs_user=request.user,
        selections=selections,
        expire_time=expire_time,
        status='pending',
    )
    return success_response({
        'id': po.id,
        'qr_url': request.build_absolute_uri(f'/api/wx/preorder/{po.id}/qrcode/'),
        'expire_time': po.expire_time,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def preorder_detail(request, po_id):
    """获取预下单详情"""
    try:
        po = PreOrder.objects.get(id=po_id, is_deleted=False)
    except PreOrder.DoesNotExist:
        return error_response(msg='预下单不存在或已过期')
    if po.expire_time and po.expire_time < timezone.now():
        if po.status == 'pending':
            po.status = 'expired'
            po.save(update_fields=['status', 'updated_at'])
        return error_response(msg='预下单已过期')
    if po.status != 'pending':
        return error_response(msg='该预下单已完成，不能重复下单')
    return success_response({
        'id': po.id,
        'selections': po.selections,
        'status': po.status,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def preorder_qrcode(request, po_id):
    """生成微信官方小程序码，扫码直达客户确认页。"""
    try:
        po = PreOrder.objects.get(id=po_id, is_deleted=False)
    except PreOrder.DoesNotExist:
        return error_response(msg='预下单不存在')

    if po.expire_time and po.expire_time <= timezone.now():
        return error_response(msg='预下单已过期')
    if po.status != 'pending':
        return error_response(msg='该预下单已完成')
    try:
        access_token = _get_wx_access_token()
        session = requests.Session()
        session.trust_env = False
        response = _wechat_https_request(
            session,
            'post',
            f'https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={access_token}',
            json={
                'scene': f'po={po.id}',
                'page': 'pages/preorder-checkout/preorder-checkout',
                'check_path': False,
                'env_version': getattr(settings, 'WX_MINI_PROGRAM_ENV_VERSION', 'release'),
                'width': 430,
            },
            timeout=15,
        )
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')
        if 'image/' not in content_type:
            payload = response.json()
            raise RuntimeError(payload.get('errmsg') or '生成小程序码失败')
        return HttpResponse(response.content, content_type='image/png')
    except Exception as exc:
        # 不输出包含 access_token / app secret 的完整请求 URL 或堆栈。
        logger.warning('生成预下单小程序码失败: %s', type(exc).__name__)
        return error_response(msg='生成小程序码失败，请稍后重试')
