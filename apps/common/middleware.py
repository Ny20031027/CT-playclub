import time
import json
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class BanCheckMiddleware(MiddlewareMixin):
    """封禁拦截：带有效 token 的封禁用户，任何请求直接返回封禁错误（踢下线）。"""

    def process_request(self, request):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return None
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            user, _ = JWTAuthentication().authenticate(request)
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
                from apps.common.response import error_response
                return error_response(
                    msg='账号已被封禁，无法操作',
                    code=4010,
                    data={
                        'banned': True,
                        'permanent': info.get('permanent', False),
                        'ban_until': info.get('ban_until'),
                        'ban_reason': info.get('ban_reason', ''),
                    },
                )
        return None


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
