from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from apps.account.models import User
from apps.common.response import success_response, error_response
from apps.customer.models import Customer, CustomerService
from apps.employee.models import Employee

from .views import (
    WxUser, get_wx_openid, get_related_profile_objects, choose_display_nickname,
    sync_profile_tables, field_file_url, Order, OrderStatus
)


def _build_profile_payload(user, related, nickname=None):
    customer = related['customer']
    employee = related['employee']
    user_type = user.get_primary_identity_code(customer=customer, employee=employee)
    avatar = (
        related['wx_user'].avatar if related['wx_user'] else ''
    ) or field_file_url(user.avatar) or field_file_url(customer.avatar if customer else '') or field_file_url(employee.avatar if employee else '')
    phone = (
        related['wx_user'].phone if related['wx_user'] else ''
    ) or user.phone or (customer.phone if customer else '') or (employee.phone if employee else '')

    payload = {
        'id': user.id,
        'nickname': nickname or choose_display_nickname(user, wx_user=related['wx_user'], customer=customer, employee=employee),
        'avatar': avatar,
        'phone': phone,
        'gender': user.gender or 'unknown',
        'user_type': user_type,
        'roles': user.get_role_codes(),
        'is_superuser': user.is_superuser,
        'customer_id': customer.id if customer else None,
        'employee_id': employee.id if employee else None,
    }

    if employee:
        has_in_progress = Order.objects.filter(
            order_members__employee=employee,
            order_members__is_deleted=False,
            order_members__status='in_progress',
            status='in_progress',
            is_deleted=False,
        ).exists()
        payload.update({
            'order_count': employee.order_count,
            'total_spent': 0,
            'balance': 0,
            'is_busy': has_in_progress,
            'status': 'busy' if has_in_progress else 'idle',
            'level_num': employee.level_num,
            'intro': employee.intro or '',
            'commission_balance': float(employee.commission_balance),
            'tags': [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in employee.tags.filter(status=True)],
        })
    elif customer:
        payload.update({
            'order_count': Order.objects.filter(customer=customer, is_deleted=False).count(),
            'total_spent': float(
                Order.objects.filter(
                    customer=customer,
                    status__in=[OrderStatus.COMPLETED, OrderStatus.REVIEWED],
                    is_deleted=False,
                ).aggregate(sum=Sum('pay_amount'))['sum'] or 0
            ),
            'balance': float(customer.balance) if customer.balance else 0,
            'is_busy': False,
            'status': 'idle',
            'level_num': 0,
            'intro': '',
            'commission_balance': 0,
            'tags': [],
        })

    return payload


@api_view(['POST'])
@permission_classes([AllowAny])
def wx_login(request):
    code = request.data.get('code')
    if not code:
        return error_response(msg='缺少code参数')

    wx_data = get_wx_openid(code)
    if not wx_data:
        return error_response(msg='微信登录失败，请重试')

    openid = wx_data['openid']
    session_key = wx_data.get('session_key', '')

    wx_user, created = WxUser.objects.get_or_create(
        openid=openid,
        defaults={'session_key': session_key}
    )
    if not created:
        wx_user.session_key = session_key
        wx_user.last_login = timezone.now()
        wx_user.save(update_fields=['session_key', 'last_login'])

    if not wx_user.user:
        username = f'wx_{openid[-8:]}'
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

    related = get_related_profile_objects(user)
    user_type = user.get_primary_identity_code(
        customer=related['customer'],
        employee=related['employee'],
    )

    customer = related['customer']
    if user_type == 'customer':
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

    refresh = RefreshToken.for_user(user)
    payload = _build_profile_payload(user, get_related_profile_objects(user), nickname=display_nickname)
    return success_response({
        'token': str(refresh.access_token),
        'refresh': str(refresh),
        'user_info': payload,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def test_login(request):
    user_type = request.data.get('user_type', 'customer')

    if user_type == 'dasher':
        employee = Employee.objects.select_related('user').filter(user__customer__isnull=True).first()
        if not employee:
            return error_response(msg='没有可用的打手账号')
        user = employee.user
    elif user_type == 'cs':
        cs = CustomerService.objects.select_related('customer__user').filter(customer__user__employee__isnull=True).first()
        if not cs:
            return error_response(msg='没有可用的客服账号')
        user = cs.customer.user
    else:
        customer = Customer.objects.select_related('user').filter(
            cs_profile__isnull=True,
            user__employee__isnull=True,
        ).first()
        if not customer:
            return error_response(msg='没有可用的客户账号')
        user = customer.user

    refresh = RefreshToken.for_user(user)
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    related = get_related_profile_objects(user)
    payload = _build_profile_payload(user, related)
    return success_response({
        'token': str(refresh.access_token),
        'refresh': str(refresh),
        'user_info': payload,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    user = request.user
    related = get_related_profile_objects(user)
    nickname = choose_display_nickname(
        user,
        wx_user=related['wx_user'],
        customer=related['customer'],
        employee=related['employee'],
    )
    payload = _build_profile_payload(user, related, nickname=nickname)
    return success_response(payload)
