import json
import re
import requests
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from apps.account.models import User
from apps.employee.models import Employee, EmployeeSkill, EmployeeSkillRelation, EmployeeTag, SkillLevel
from apps.order.models import Order, OrderMember, OrderComment, OrderPrice, OrderStatus
from apps.notice.models import Notice, UserNotice
from .models import WxUser, Banner, Announcement, GameCategory, Gift
from .serializers import (
    WxUserSerializer, BannerSerializer, AnnouncementSerializer,
    GameCategorySerializer, GiftSerializer
)


class GameCategoryViewSet(BaseModelViewSet):
    """游戏分类管理（品类设置）"""
    queryset = GameCategory.objects.all()
    serializer_class = GameCategorySerializer
    filterset_fields = ['status']
    search_fields = ['name']
    ordering_fields = ['sort', 'id']
    permission_classes = [AllowAny]

# 微信小程序配置 - 需要在 settings.py 或环境变量中配置
WX_APPID = getattr(settings, 'WX_APPID', '')
WX_SECRET = getattr(settings, 'WX_SECRET', '')

ACTIVE_ORDER_MEMBER_STATUSES = ['accepted', 'in_progress']
FORMAL_ORDER_STATUSES = ['confirming', 'claimed', 'in_progress', 'completed', 'reviewed']


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
    except Exception:
        pass
    try:
        objects['employee'] = user.employee
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
        employee = user.employee
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

    if order.status == 'published' and effective_locked_slots >= int(order.quantity or 0) and effective_locked_slots > 0:
        order.status = 'confirming'
        updated_fields.append('status')

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
        'can_transfer': order.status in ['claimed', 'in_progress'] and is_leader,
        'can_discount': order.status in ['claimed', 'in_progress'] and is_leader,
        'can_manage_order': is_leader,
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

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    # 自动创建客户记录（如果不存在）
    from apps.customer.models import Customer
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
        # 更新客户信息
        if wx_user.nickname and customer.nickname != wx_user.nickname:
            customer.nickname = wx_user.nickname
        if wx_user.avatar and customer.avatar != wx_user.avatar:
            customer.avatar = wx_user.avatar
        if wx_user.phone and customer.phone != wx_user.phone:
            customer.phone = wx_user.phone
        customer.save()

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
        avatar=wx_user.avatar or field_file_url(user.avatar) or field_file_url(customer.avatar),
        phone=wx_user.phone or user.phone or customer.phone,
    )

    # 生成 JWT token
    refresh = RefreshToken.for_user(user)
    token = str(refresh.access_token)

    # 判断用户身份
    user_type = 'customer'
    try:
        if hasattr(user, 'employee'):
            user_type = 'dasher'
    except Exception:
        pass

    return success_response({
        'token': token,
        'refresh': str(refresh),
        'user_info': {
            'id': user.id,
            'nickname': display_nickname,
            'avatar': wx_user.avatar or field_file_url(user.avatar) or field_file_url(customer.avatar),
            'phone': wx_user.phone or user.phone or customer.phone or '',
            'gender': user.gender or 'unknown',
            'user_type': user_type,
            'customer_id': customer.id if customer else None,
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
            employee = Employee.objects.select_related('user').first()
            if not employee:
                return error_response(msg='没有打手账号，请先在后台创建')
            user = employee.user
        except Exception:
            return error_response(msg='打手账号不存在')
    elif user_type == 'cs':
        # 登录客服账号
        try:
            from apps.customer.models import CustomerService
            cs = CustomerService.objects.select_related('customer__user').first()
            if not cs:
                return error_response(msg='没有客服账号，请先在后台创建')
            user = cs.customer.user
        except Exception:
            return error_response(msg='客服账号不存在')
    else:
        # 登录客户账号
        try:
            from apps.customer.models import Customer
            customer = Customer.objects.select_related('user').first()
            if not customer:
                return error_response(msg='没有客户账号，请先在后台创建')
            user = customer.user
        except Exception:
            return error_response(msg='客户账号不存在')

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
        for rel in emp.skill_relations.filter(skill__status=True).select_related('skill')[:3]:
            skills.append({
                'name': rel.skill.name,
                'price': float(rel.unit_price),
            })
        # 获取评价数量
        review_count = OrderComment.objects.filter(employee=emp, is_deleted=False).count()

        employee_list.append({
            'id': emp.id,
            'nickname': emp.nickname or emp.real_name,
            'avatar': employee_avatar_url(emp),
            'gender': emp.gender,
            'level': emp.level,
            'level_num': emp.level_num,
            'rating': float(emp.rating),
            'review_count': review_count,
            'order_count': emp.order_count,
            'intro': emp.intro[:50] if emp.intro else '',
            'skills': skills,
            'is_online': emp.online_status,
        })

    return success_response({
        'banners': BannerSerializer(banners, many=True, context={'request': request}).data,
        'announcements': AnnouncementSerializer(announcements, many=True).data,
        'games': GameCategorySerializer(games, many=True, context={'request': request}).data,
        'employees': employee_list,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def game_list(request):
    """游戏分类列表（与首页共用）"""
    games = GameCategory.objects.filter(status=True, is_deleted=False).order_by('sort', 'id')
    return success_response(GameCategorySerializer(games, many=True, context={'request': request}).data)


# ============ 陪玩师模块 ============

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
    ).select_related('user', 'user__wx_user').prefetch_related('skills', 'tags')

    if skill_id:
        queryset = queryset.filter(skill_relations__skill_id=skill_id)
    if game_id:
        queryset = queryset.filter(
            skill_relations__skill__game_category_id=game_id,
            skill_relations__skill__status=True
        )
    if level:
        queryset = queryset.filter(level=level)
    if gender:
        queryset = queryset.filter(gender=gender)
    if keyword:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(nickname__icontains=keyword) |
            Q(real_name__icontains=keyword) |
            Q(intro__icontains=keyword)
        )

    # 排序
    sort_map = {
        'rating': '-rating',
        'order_count': '-order_count',
        'price': 'skill_relations__unit_price',
        'new': '-created_at',
    }
    order_field = sort_map.get(sort_by, '-rating')
    queryset = queryset.order_by(order_field).distinct()

    total = queryset.count()
    start = (page - 1) * page_size
    employees = queryset[start:start + page_size]

    employee_list = []
    for emp in employees:
        skills = []
        for rel in emp.skill_relations.filter(skill__status=True).select_related('skill', 'skill_level')[:5]:
            skills.append({
                'id': rel.skill.id,
                'name': rel.skill.name,
                'price': float(rel.unit_price),
                'level': rel.skill_level.name if rel.skill_level else '',
            })
        tags = [{'name': t.name, 'color': t.color} for t in emp.tags.filter(status=True)[:5]]
        # 获取评价数量
        review_count = OrderComment.objects.filter(employee=emp, is_deleted=False).count()

        employee_list.append({
            'id': emp.id,
            'nickname': emp.nickname or emp.real_name,
            'avatar': employee_avatar_url(emp),
            'gender': emp.gender if emp.gender != 'unknown' else (emp.user.gender if emp.user else 'unknown'),
            'age': emp.age,
            'level': emp.level,
            'level_num': emp.level_num,
            'rating': float(emp.rating),
            'review_count': review_count,
            'order_count': emp.order_count,
            'intro': emp.intro[:80] if emp.intro else '',
            'skills': skills,
            'tags': tags,
            'is_online': emp.online_status,
        })

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
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

    skills = []
    for rel in emp.skill_relations.filter(skill__status=True).select_related('skill', 'skill_level'):
        skills.append({
            'id': rel.skill.id,
            'name': rel.skill.name,
            'category': rel.skill.category,
            'price': float(rel.unit_price),
            'level': rel.skill_level.name if rel.skill_level else '',
        })

    tags = [{'name': t.name, 'color': t.color} for t in emp.tags.filter(status=True)]

    # 最近评价
    comments = OrderComment.objects.filter(
        employee=emp, is_deleted=False
    ).select_related('customer').order_by('-created_at')[:5]
    comment_list = []
    for c in comments:
        # 将逗号分隔的标签字符串转换为数组
        tags_list = [t.strip() for t in c.tags.split(',') if t.strip()] if c.tags else []
        comment_list.append({
            'id': c.id,
            'rating': c.rating,
            'content': c.content,
            'tags': tags_list,
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
        'nickname': emp.nickname or emp.real_name,
        'real_name': emp.real_name,
        'avatar': employee_avatar_url(emp),
        'gender': emp.gender,
        'age': emp.age,
        'level': emp.level,
        'level_num': emp.level_num,
        'rating': float(emp.rating),
        'order_count': emp.order_count,
        'total_duration': emp.total_duration,
        'intro': emp.intro or '',
        'skills': skills,
        'tags': tags,
        'comments': comment_list,
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

    # 计算价格
    unit_price = 0
    if employee_id:
        try:
            relation = EmployeeSkillRelation.objects.get(employee_id=employee_id, skill_id=skill_id)
            unit_price = float(relation.unit_price)
        except EmployeeSkillRelation.DoesNotExist:
            pass

    if unit_price == 0:
        price_obj = OrderPrice.objects.filter(skill_id=skill_id, status=True).first()
        if price_obj:
            unit_price = float(price_obj.unit_price)

    total_amount = unit_price * duration / 60 * quantity if unit_price else 0

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
def create_self_service_order(request):
    """客户自助下单"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        from apps.customer.models import Customer
        customer = Customer.objects.create(
            user=user,
            nickname=user.nickname or f'用户{user.id}',
        )

    title = request.data.get('title', '')
    game_name = request.data.get('game_name', '')
    game_id = request.data.get('game_id', '')
    content = request.data.get('content', '')
    price = request.data.get('price', 0)
    duration = request.data.get('duration', 60)
    quantity = request.data.get('quantity', 1)

    if not title:
        return error_response(msg='请输入订单标题')

    # 生成订单号
    import random
    random_suffix = random.randint(1000, 9999)
    order_no = f'SV{timezone.now().strftime("%Y%m%d%H%M%S")}{str(user.id).zfill(4)}{random_suffix}'

    order = Order.objects.create(
        order_no=order_no,
        customer=customer,
        status=OrderStatus.PUBLISHED,
        title=title,
        order_type='self_service',
        duration=duration,
        quantity=quantity,
        unit_price=price,
        total_amount=float(price) * duration / 60 * quantity if price else 0,
        pay_amount=float(price) * duration / 60 * quantity if price else 0,
        game_id=game_id,
        game_name=game_name,
        remark=content,
        platform='mini_program',
    )

    return success_response({
        'order_id': order.id,
        'order_no': order.order_no,
        'total_amount': float(order.total_amount),
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
        try:
            current_employee = request.user.employee
        except Exception:
            pass

    queryset = Order.objects.filter(
        status='published',
        is_deleted=False
    )

    if game_name:
        queryset = queryset.filter(game_name=game_name)
    if keyword:
        from django.db.models import Q
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
        if o.status != 'published':
            continue
        remaining_slots = get_remaining_slots(o)
        # 只显示还有剩余席位的订单
        if remaining_slots <= 0:
            continue

        # 如果是预约订单，只显示给被预约的打手
        if o.assigned_employee_id and current_employee and o.assigned_employee_id != current_employee.id:
            continue

        # 检查当前打手是否已预订该订单
        my_claimed = False
        my_claimed_slots = 0
        if request.user.is_authenticated:
            try:
                employee = request.user.employee
                member = OrderMember.objects.filter(
                    order=o, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
                ).first()
                if member:
                    my_claimed = True
                    my_claimed_slots = parse_member_slots(member)
            except Exception:
                pass

        # 判断是否为预约订单（只能被预约的打手接取）
        is_reserved = bool(o.assigned_employee_id)
        can_claim = not is_reserved or (current_employee and o.assigned_employee_id == current_employee.id)

        order_list.append({
            'id': o.id,
            'order_no': o.order_no,
            'title': o.title,
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
            'my_claimed_slots': my_claimed_slots,
            'transfer_reason': o.transfer_reason or '',
            'is_transfer': bool(o.transfer_reason),
            'is_reserved': is_reserved,
            'can_claim': can_claim,
            'assigned_employee_name': o.assigned_employee.nickname if o.assigned_employee else '',
        })
                'can_claim': can_claim,
                'assigned_employee_name': o.assigned_employee.nickname if o.assigned_employee else '',
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

    queryset = Order.objects.filter(customer=customer, is_deleted=False)

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
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='非陪玩师账号')

    order_status = request.GET.get('status')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    # 只显示打手已接取的订单
    queryset = Order.objects.filter(
        order_members__employee=employee,
        order_members__is_deleted=False,
        order_members__status__in=ACTIVE_ORDER_MEMBER_STATUSES,
        is_deleted=False
    ).distinct()

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
    is_dasher = False
    try:
        employee = user.employee
        is_dasher = True
    except Exception:
        pass

    try:
        if is_dasher:
            # 打手可以查看：可接取的订单(published) + 自己已接取的订单
            from django.db.models import Q
            order_qs = Order.objects.filter(
                Q(id=order_id) & (
                    Q(status='published') | Q(
                        order_members__employee=employee,
                        order_members__is_deleted=False,
                        order_members__status__in=ACTIVE_ORDER_MEMBER_STATUSES,
                    )
                ),
                is_deleted=False
            ).distinct()
            order = order_qs.select_related('skill', 'customer').prefetch_related(
                'order_members__employee', 'comment'
            ).first()
        else:
            # 客户只能查看自己的订单
            customer = user.customer
            order = Order.objects.filter(
                id=order_id, customer=customer, is_deleted=False
            ).select_related('skill', 'customer').prefetch_related(
                'order_members__employee', 'comment'
            ).first()
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    if order is None:
        return error_response(msg='订单不存在')

    sync_order_seat_state(order)
    ensure_order_leader(order)

    members = []
    for m in order.order_members.filter(is_deleted=False):
        slots = parse_member_slots(m)
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
        })

    comment = None
    if hasattr(order, 'comment') and order.comment:
        c = order.comment
        # 将逗号分隔的标签字符串转换为数组
        tags_list = [t.strip() for t in c.tags.split(',') if t.strip()] if c.tags else []
        comment = {
            'id': c.id,
            'rating': c.rating,
            'content': c.content,
            'tags': tags_list,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    # 检查当前打手是否已预订该订单
    my_booking = None
    if is_dasher:
        my_booking = OrderMember.objects.filter(
            order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
        ).first()

    # 获取队长信息
    leader_id = order.leader_id if order.leader else None
    action_flags = build_dasher_order_flags(order, employee if is_dasher else None)
    remaining_slots = get_remaining_slots(order)
    my_booking_slots = parse_member_slots(my_booking) if my_booking else 0

    return success_response({
        'id': order.id,
        'order_no': order.order_no,
        'skill_name': order.skill.name if order.skill else '',
        'status': order.status,
        'status_display': order.get_status_display(),
        'order_type': order.order_type,
        'duration': order.duration,
        'quantity': order.quantity,
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
        'transfer_reason': order.transfer_reason or '',
        'is_transfer': bool(order.transfer_reason),
        'members': members,
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
    """打手领取订单
    规则：
    - 第一个接取的人自动成为队长
    - 队长可以锁定多个席位，但只占1个席位
    - 锁定的席位其他打手无法接取，只能由队长邀请填满
    - 只有所有席位都被实际接取后，订单才进入确认状态
    """
    user = request.user
    try:
        employee = user.employee
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

    # 计算剩余可接取的席位（未被锁定的）
    remaining_slots = get_remaining_slots(order)
    if remaining_slots <= 0:
        return error_response(msg='该订单席位已满')

    # 检查该打手是否已经接取过此订单
    existing_member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()
    if existing_member:
        return error_response(msg='您已经接取过该订单')

    # 判断是否为第一个接取者（将成为队长）
    is_first_claimer = not order.leader

    # 获取打手要锁定的席位数
    slots = request.data.get('slots', 1)
    slots = int(slots) if slots else 1

    # 验证席位数
    if slots <= 0:
        return error_response(msg='锁定席位数必须大于0')
    
    if is_first_claimer:
        # 队长可以锁定席位（包括自己的），但最多不能超过总需求
        if slots > order.quantity:
            return error_response(msg=f'最多可锁定{order.quantity}个席位')
    else:
        # 非队长只能接取1个席位
        if slots > 1:
            return error_response(msg='非队长只能接取1个席位，剩余席位需由队长邀请分配')
        if slots > remaining_slots:
            return error_response(msg=f'剩余席位不足，当前剩余{remaining_slots}个席位')

    # 计算金额（按席位比例）
    amount_per_slot = order.pay_amount / order.quantity if order.quantity > 0 else 0

    # 创建订单成员记录（队长只占1个席位）
    member = OrderMember.objects.create(
        order=order,
        employee=employee,
        skill=order.skill,
        unit_price=order.unit_price,
        duration=order.duration,
        amount=round(amount_per_slot, 2),
        status='accepted',
        remark=f'slots:{slots}',
    )

    # 更新已锁定席位数（队长锁定的总数）
    order.locked_slots = slots

    # 如果是第一个接取的人，设为队长
    if not order.leader:
        order.leader = employee

    order.save(update_fields=['locked_slots', 'leader', 'updated_at'])

    # 计算实际接取的人数（不包括锁定的）
    actual_members = OrderMember.objects.filter(
        order=order, is_deleted=False, status__in=['accepted', 'in_progress']
    ).count()
    
    # 剩余需要邀请的人数
    remaining_to_invite = order.quantity - actual_members

    if remaining_to_invite <= 0:
        # 所有席位都被实际接取，订单进入确认状态
        order.status = 'confirming'
        order.save(update_fields=['status', 'updated_at'])
        return success_response(
            msg='所有打手已就位，订单正式接取',
            data={'locked_slots': order.locked_slots, 'status': 'confirming', 'member_id': member.id}
        )
    else:
        if is_first_claimer:
            msg = f'已锁定{slots}个席位，还需邀请{remaining_to_invite}名打手'
        else:
            msg = f'已接取1个席位，还需{remaining_to_invite}名打手就位'
        return success_response(
            msg=msg,
            data={'locked_slots': order.locked_slots, 'remaining_slots': remaining_to_invite, 'member_id': member.id}
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invite_order_member(request, order_id):
    """邀请打手接取订单席位；邀请本身不锁定席位。"""
    user = request.user
    try:
        employee = user.employee
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
        employee = user.employee
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
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查是否是队长
    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以转单')

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
        active_member.employee.status = 'idle'
        active_member.employee.save(update_fields=['status'])
    OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).delete()

    # 更新订单状态为可接取
    order.status = 'published'
    order.locked_slots = 0
    order.leader = None
    order.customer_confirmed = False
    order.dasher_confirmed = False
    order.transfer_reason = transfer_reason
    order.save(update_fields=[
        'status', 'locked_slots', 'leader', 'customer_confirmed',
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
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查是否是队长
    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以免单')

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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_order(request, order_id):
    """完结订单"""
    user = request.user
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.get(id=order_id, status='in_progress', is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在或状态不正确')

    if order.leader_id != employee.id:
        return error_response(msg='只有队长可以完结订单')

    order.status = 'completed'
    order.end_time = timezone.now()
    order.complete_time = timezone.now()
    order.save(update_fields=['status', 'end_time', 'complete_time', 'updated_at'])

    # 更新打手状态为空闲
    for member in order.order_members.filter(is_deleted=False):
        member.status = 'completed'
        member.end_time = timezone.now()
        member.save(update_fields=['status', 'end_time'])
        member.employee.status = 'idle'
        member.employee.save(update_fields=['status'])

    return success_response(msg='订单已完结')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_order(request, order_id):
    """打手开始订单（只有队长可以开始）"""
    user = request.user
    try:
        employee = user.employee
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

    return success_response(msg='订单已开始')


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

    # 更新订单状态为已完成
    order.status = 'completed'
    order.end_time = timezone.now()
    order.complete_time = timezone.now()
    order.save(update_fields=['status', 'end_time', 'complete_time', 'updated_at'])

    # 更新打手状态为空闲
    for member in order.order_members.filter(is_deleted=False):
        member.status = 'completed'
        member.end_time = timezone.now()
        member.save(update_fields=['status', 'end_time'])
        member.employee.status = 'idle'
        member.employee.save(update_fields=['status'])

    return success_response(msg='订单已结束')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_order(request, order_id):
    """评价订单"""
    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    try:
        order = Order.objects.get(id=order_id, customer=customer, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    if order.status != OrderStatus.COMPLETED:
        return error_response(msg='订单未完成，无法评价')

    rating = request.data.get('rating', 5)
    content = request.data.get('content', '')
    tags = request.data.get('tags', '')
    is_anonymous = request.data.get('is_anonymous', False)

    member = order.order_members.first()
    employee = member.employee if member else None

    comment, created = OrderComment.objects.get_or_create(
        order=order,
        defaults={
            'customer': customer,
            'employee': employee,
            'rating': rating,
            'content': content,
            'tags': tags,
            'is_anonymous': is_anonymous,
        }
    )
    if not created:
        comment.rating = rating
        comment.content = content
        comment.tags = tags
        comment.is_anonymous = is_anonymous
        comment.save()

    order.status = OrderStatus.REVIEWED
    order.save(update_fields=['status', 'updated_at'])

    # 更新陪玩师评分
    if employee:
        from django.db.models import Avg
        avg = OrderComment.objects.filter(employee=employee).aggregate(avg=Avg('rating'))['avg']
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

    return success_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'list': notice_list,
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

    if not content:
        return error_response(msg='消息内容不能为空')

    # 获取在线客服
    from apps.customer.models import CustomerService
    cs_user = CustomerService.objects.filter(status='online').select_related('customer__user').first()

    message = CSMessage.objects.create(
        customer=customer,
        cs_user=cs_user.customer.user if cs_user else None,
        content=content,
        msg_type=msg_type,
        sender_type='customer',
    )

    return success_response(msg='发送成功', data={'message_id': message.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_messages(request):
    """获取客服消息列表"""
    from apps.customer.models import CSMessage

    user = request.user
    try:
        customer = user.customer
    except Exception:
        return error_response(msg='用户不存在')

    messages = CSMessage.objects.filter(customer=customer).order_by('created_at')
    data = []
    for msg in messages:
        data.append({
            'id': msg.id,
            'content': msg.content,
            'msg_type': msg.msg_type,
            'sender_type': msg.sender_type,
            'is_read': msg.is_read,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    # 标记为已读
    messages.filter(sender_type='cs', is_read=False).update(is_read=True)

    return success_response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_unread_count(request):
    """获取未读客服消息数"""
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
    """获取客服聊天列表（按客户分组）"""
    from apps.customer.models import CSMessage, Customer, CustomerService

    user = request.user
    try:
        cs = CustomerService.objects.get(customer__user=user)
    except CustomerService.DoesNotExist:
        return error_response(msg='您不是客服')

    # 获取所有有消息的客户
    customer_ids = CSMessage.objects.values_list('customer_id', flat=True).distinct()
    customers = Customer.objects.filter(id__in=customer_ids)

    chat_list = []
    for customer in customers:
        # 获取最后一条消息
        last_msg = CSMessage.objects.filter(customer=customer).order_by('-created_at').first()
        # 获取未读消息数
        unread_count = CSMessage.objects.filter(customer=customer, sender_type='customer', is_read=False).count()

        # 处理客户头像
        customer_avatar = ''
        if customer.avatar:
            avatar_str = str(customer.avatar)
            if avatar_str.startswith('http'):
                customer_avatar = avatar_str
            else:
                customer_avatar = str(customer.avatar) if customer.avatar else ''

        chat_list.append({
            'customer_id': customer.id,
            'customer_name': customer.nickname,
            'customer_avatar': customer_avatar,
            'last_message': last_msg.content if last_msg else '',
            'last_message_time': last_msg.created_at.strftime('%H:%M') if last_msg else '',
            'unread_count': unread_count,
        })

    # 按最后消息时间排序
    chat_list.sort(key=lambda x: x['last_message_time'], reverse=True)

    return success_response(chat_list)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cs_chat_messages(request):
    """获取客服与某个客户的聊天记录"""
    from apps.customer.models import CSMessage, Customer

    customer_id = request.GET.get('customer_id')
    if not customer_id:
        return error_response(msg='缺少客户ID')

    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return error_response(msg='客户不存在')

    messages = CSMessage.objects.filter(customer=customer).order_by('created_at')
    data = []
    for msg in messages:
        data.append({
            'id': msg.id,
            'content': msg.content,
            'msg_type': msg.msg_type,
            'sender_type': msg.sender_type,
            'is_read': msg.is_read,
            'created_at': msg.created_at.strftime('%H:%M'),
        })

    # 标记消息为已读
    messages.filter(sender_type='customer', is_read=False).update(is_read=True)

    # 返回客户头像
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
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_cs_reply(request):
    """客服回复消息"""
    import logging
    logger = logging.getLogger(__name__)
    
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
    logger.info(f'收到消息: customer_id={customer_id}, content={content}')

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

    message = CSMessage.objects.create(
        customer=customer,
        cs_user=user,
        content=content,
        msg_type='text',
        sender_type='cs',
    )
    logger.info(f'消息已保存: message_id={message.id}')

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
    try:
        if employee_obj:
            user_type = 'dasher'
    except Exception:
        pass

    # 统计数据
    order_count = 0
    total_spent = 0
    balance = 0
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
        except Exception:
            order_count = 0
            total_spent = 0
            balance = 0
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
        'is_busy': is_busy,
        'status': 'busy' if is_busy else 'idle',
        'level_num': employee_obj.level_num if employee_obj else 0,
        'intro': employee_obj.intro if employee_obj else '',
        'commission_balance': float(employee_obj.commission_balance) if employee_obj else 0,
        'tags': tags,
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
    
    logger.info(f'Update profile: user={user.id}, nickname={nickname}, gender={gender}, avatar={bool(avatar)}')

    sync_profile_tables(user, nickname=nickname, avatar=avatar, gender=gender)

    # 如果是打手，保存个人介绍
    if intro is not None:
        try:
            employee = user.employee
            employee.intro = intro
            employee.save(update_fields=['intro'])
        except Exception:
            pass

    # 如果是打手，保存标签
    tags = request.data.get('tags')
    if tags is not None:
        try:
            employee = user.employee
            employee.tags.set(tags)
        except Exception:
            pass

    return success_response(msg='更新成功')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_skills(request):
    """获取打手自己的技能设置"""
    user = request.user
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    relations = EmployeeSkillRelation.objects.filter(employee=employee).select_related(
        'skill', 'skill__game_category', 'skill_level')
    my_skills = []
    for rel in relations:
        my_skills.append({
            'id': rel.id,
            'skill_id': rel.skill.id,
            'name': rel.skill.name,
            'category': rel.skill.category,
            'game_name': rel.skill.game_category.name if rel.skill.game_category else '',
            'game_id': rel.skill.game_category.id if rel.skill.game_category else 0,
            'skill_level_id': rel.skill_level.id if rel.skill_level else 0,
            'level_name': rel.skill_level.name if rel.skill_level else '',
            'unit_price': float(rel.unit_price),
        })

    return success_response(data=my_skills)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_skills(request):
    """获取所有可用技能列表（含段位）"""
    skills = EmployeeSkill.objects.filter(status=True).select_related('game_category').prefetch_related('levels')
    data = []
    for s in skills:
        levels = []
        for lv in s.levels.all().order_by('sort', 'id'):
            levels.append({
                'id': lv.id,
                'name': lv.name,
                'price_min': float(lv.price_min),
                'price_max': float(lv.price_max),
                'sort': lv.sort,
            })
        data.append({
            'id': s.id,
            'name': s.name,
            'category': s.category,
            'game_name': s.game_category.name if s.game_category else '',
            'game_id': s.game_category.id if s.game_category else 0,
            'levels': levels,
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
    """更新打手技能设置（增删改）"""
    user = request.user
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    skills_data = request.data.get('skills', [])

    # 先清空旧的
    EmployeeSkillRelation.objects.filter(employee=employee).delete()

    # 写入新的
    for item in skills_data:
        skill_id = item.get('skill_id')
        unit_price = item.get('unit_price', 0)
        skill_level_id = item.get('skill_level_id', 0)

        if not skill_id:
            continue

        try:
            skill = EmployeeSkill.objects.get(id=skill_id)
        except EmployeeSkill.DoesNotExist:
            continue

        skill_level = None
        if skill_level_id:
            try:
                skill_level = SkillLevel.objects.get(id=skill_level_id, skill=skill)
            except SkillLevel.DoesNotExist:
                pass

        EmployeeSkillRelation.objects.create(
            employee=employee,
            skill=skill,
            skill_level=skill_level,
            unit_price=unit_price,
        )

    return success_response(msg='技能设置保存成功')


# ============ 组队模块 ============

from apps.employee.models import Team, TeamMember


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_team(request):
    """获取我的组队信息"""
    user = request.user
    try:
        employee = user.employee
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
        employee = user.employee
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
        employee = user.employee
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

    # 检查目标是否已在队伍中
    if TeamMember.objects.filter(team=team, employee=target, status__in=['active', 'invited']).exists():
        return error_response(msg='该打手已在队伍中')

    # 检查目标是否有队伍
    if TeamMember.objects.filter(employee=target, status='active').exists():
        return error_response(msg='该打手已在其他队伍中')

    # 创建邀请
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
        employee = user.employee
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
        employee = user.employee
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
