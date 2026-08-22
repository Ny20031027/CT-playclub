import time
import json
import logging
import datetime
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

logger = logging.getLogger(__name__)


class BanCheckMiddleware(MiddlewareMixin):
    """封禁拦截：带有效 token 的封禁用户，任何请求直接返回封禁错误（踢下线）。"""

    def process_request(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return None
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            user, validated_token = JWTAuthentication().authenticate(request)
        except Exception as exc:
            # token 无效/过期，或底层（如数据库未迁移/不可用）异常：放行，交给后续 DRF 处理
            logger.warning('BanCheck authenticate skipped: %s', exc)
            return None
        if user is not None:
            try:
                banned = user.is_banned_active()
            except Exception as exc:
                logger.warning('BanCheck is_banned_active error: %s', exc)
                banned = False
            if banned:
                from apps.account.ban_utils import ban_info
                info = ban_info(user)
                return JsonResponse({
                    'code': 4010,
                    'msg': '账号已被封禁，无法操作',
                    'data': {
                        'banned': True,
                        'permanent': info.get('permanent', False),
                        'ban_until': info.get('ban_until'),
                        'ban_until_display': info.get('ban_until_display'),
                        'ban_reason': info.get('ban_reason', ''),
                    },
                })
            invalid_before = getattr(user, 'auth_invalid_before', None)
            token_issued_at = validated_token.get('iat') if validated_token else None
            if invalid_before and token_issued_at:
                issued_at = datetime.datetime.fromtimestamp(
                    int(token_issued_at), tz=datetime.timezone.utc
                )
                compare_before = invalid_before
                if timezone.is_naive(compare_before):
                    compare_before = timezone.make_aware(
                        compare_before, timezone.get_current_timezone()
                    )
                if issued_at < compare_before:
                    return JsonResponse({
                        'code': 401,
                        'msg': '登录状态已失效，请重新登录',
                        'data': {'session_revoked': True},
                    })
        return None


class OAPermissionMiddleware(MiddlewareMixin):
    """OA后台权限拦截：只控制后台管理API，小程序API不走这套角色体系。"""

    def process_request(self, request):
        try:
            from apps.account.oa_permissions import required_permission_for_request, user_has_permission
        except Exception as exc:
            logger.warning('OAPermission import skipped: %s', exc)
            return None

        permission_code = required_permission_for_request(request.path, request.method)
        if not permission_code:
            return None

        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return None

        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                auth_result = JWTAuthentication().authenticate(request)
                if auth_result:
                    user, _ = auth_result
                    request.user = user
            except Exception as exc:
                logger.warning('OAPermission authenticate skipped: %s', exc)
                return None

        if user_has_permission(user, permission_code):
            return None

        return JsonResponse({
            'code': 403,
            'msg': '当前账号没有该功能权限，请联系老板或总管理调整权限',
            'data': {'permission': permission_code},
        }, status=403)


class OperationLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            try:
                user = getattr(request, 'user', None)
                if user and user.is_authenticated:
                    from apps.system.models import OperationLog
                    OperationLog.objects.create(
                        user=user,
                        method=request.method,
                        path=request.path,
                        ip=self.get_client_ip(request),
                        status_code=response.status_code,
                    )
            except Exception:
                pass
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip


class RequestLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                f"[{request.method}] {request.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration:.3f}s - "
                f"IP: {self.get_client_ip(request)}"
            )
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
