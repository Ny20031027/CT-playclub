import secrets

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.db import models
from django.utils import timezone
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import User, Role, Permission, Department, LoginLog
from .serializers import (
    LoginSerializer, WxLoginSerializer, UserInfoSerializer, UserSerializer,
    RoleSerializer, PermissionSerializer, DepartmentSerializer,
    LoginLogSerializer
)


class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.ensure_display_id()
        user.auth_invalid_before = timezone.now().replace(microsecond=0)
        user.session_key = secrets.token_urlsafe(24)
        user.save(update_fields=['auth_invalid_before', 'session_key'])

        refresh = RefreshToken.for_user(user)
        refresh['session_key'] = user.session_key
        access = refresh.access_token
        access['session_key'] = user.session_key

        LoginLog.objects.create(
            user=user,
            username=user.username,
            ip=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            status=True,
            message='登录成功'
        )

        user.is_online = True
        user.last_login_ip = self.get_client_ip(request)
        user.last_login = timezone.now()
        user.save(update_fields=['is_online', 'last_login_ip', 'last_login'])

        data = {
            'token': str(access),
            'refresh': str(refresh),
            'user_info': UserInfoSerializer(user).data
        }
        return success_response(data)

    @action(detail=False, methods=['post'], url_path='wx-login')
    def wx_login(self, request):
        """微信小程序登录"""
        serializer = WxLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.ensure_display_id()

        LoginLog.objects.create(
            user=user,
            username=user.username,
            ip=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            status=True,
            message='微信登录成功'
        )

        user.is_online = True
        user.last_login_ip = self.get_client_ip(request)
        user.save(update_fields=['is_online', 'last_login_ip'])

        data = {
            'token': serializer.validated_data['access'],
            'refresh': serializer.validated_data['refresh'],
            'user_info': UserInfoSerializer(user).data
        }
        return success_response(data)

    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        try:
            user = request.user
            if user and user.is_authenticated:
                user.is_online = False
                user.save(update_fields=['is_online'])
            return success_response(msg='退出成功')
        except Exception as e:
            return error_response(msg=str(e))

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip


class UserViewSet(BaseModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ['is_active', 'is_online']
    search_fields = ['username', 'nickname', 'phone', 'display_id']
    ordering_fields = ['id', 'username', 'created_at', 'last_login']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('web_only') == '1':
            queryset = queryset.filter(
                models.Q(is_superuser=True) |
                models.Q(is_staff=True) |
                models.Q(roles__code__in=['owner', 'admin', 'general_manager', 'finance', 'platform_lead', 'platform_staff'])
            ).distinct()
        return queryset

    def _is_owner_actor(self):
        from .oa_permissions import user_is_owner
        return user_is_owner(self.request.user)

    def _ensure_can_manage_user(self, target_user=None, role_ids=None):
        if self._is_owner_actor():
            return

        protected_role_codes = {'owner', 'admin', 'finance'}
        if target_user is not None:
            if target_user.is_superuser:
                raise PermissionDenied('只有老板账号可以管理超级管理员')
            current_role_codes = set(target_user.get_role_codes())
            if current_role_codes.intersection(protected_role_codes):
                raise PermissionDenied('只有老板账号可以管理老板或财务账号')

        if role_ids is not None:
            if role_ids == '':
                role_ids = []
            elif not isinstance(role_ids, (list, tuple, set)):
                role_ids = [role_ids]
            target_role_codes = set(
                Role.objects.filter(id__in=role_ids, status=True, is_deleted=False)
                .values_list('code', flat=True)
            )
            web_role_codes = {'owner', 'admin', 'general_manager', 'finance', 'platform_lead', 'platform_staff'}
            if target_role_codes.difference(web_role_codes):
                raise PermissionDenied('网站登录账号只能分配后台管理角色')
            if target_role_codes.intersection(protected_role_codes):
                raise PermissionDenied('只有老板账号可以分配老板或财务角色')

    @staticmethod
    def _kick_user_sessions(user):
        user.auth_invalid_before = timezone.now().replace(microsecond=0)
        user.session_key = ''
        user.is_online = False
        user.save(update_fields=['auth_invalid_before', 'session_key', 'is_online'])

    def create(self, request, *args, **kwargs):
        self._ensure_can_manage_user(role_ids=request.data.get('roles'))
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        role_ids = request.data.get('roles') if 'roles' in request.data else None
        user = self.get_object()
        self._ensure_can_manage_user(user, role_ids=role_ids)
        response = super().update(request, *args, **kwargs)
        if 'password' in request.data or request.data.get('is_active') is False:
            self._kick_user_sessions(user)
        return response

    def partial_update(self, request, *args, **kwargs):
        role_ids = request.data.get('roles') if 'roles' in request.data else None
        user = self.get_object()
        self._ensure_can_manage_user(user, role_ids=role_ids)
        response = super().partial_update(request, *args, **kwargs)
        if 'password' in request.data or request.data.get('is_active') is False:
            self._kick_user_sessions(user)
        return response

    def destroy(self, request, *args, **kwargs):
        self._ensure_can_manage_user(self.get_object())
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='display-id', permission_classes=[IsAdminUser])
    def update_display_id(self, request, pk=None):
        user = self.get_object()
        self._ensure_can_manage_user(user)
        serializer = self.get_serializer(
            user, data={'display_id': request.data.get('display_id')}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(self.get_serializer(user).data, msg='黑金ID更新成功')

    @action(detail=False, methods=['get'], url_path='info')
    def user_info(self, request):
        serializer = UserInfoSerializer(request.user)
        return success_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='menus')
    def menus(self, request):
        menus = request.user.get_user_menus()
        top_menus = menus.filter(parent__isnull=True).order_by('sort', 'id')
        data = PermissionSerializer(top_menus, many=True).data
        return success_response(data)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        perms = request.user.get_user_permissions()
        return success_response(list(perms))

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        self._ensure_can_manage_user(user)
        password = request.data.get('password', '123456')
        user.set_password(password)
        user.save()
        self._kick_user_sessions(user)
        return success_response(msg='密码重置成功')

    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not user.check_password(old_password):
            return error_response(msg='原密码错误')
        user.set_password(new_password)
        user.save()
        self._kick_user_sessions(user)
        return success_response(msg='密码修改成功')


class RoleViewSet(BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filterset_fields = ['status', 'name']
    search_fields = ['name', 'code']


class PermissionViewSet(BaseModelViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    filterset_fields = ['type', 'status']
    search_fields = ['name', 'code']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).order_by('sort', 'id')
        top_perms = queryset.filter(parent__isnull=True)
        serializer = self.get_serializer(top_perms, many=True)
        return success_response(serializer.data)


class DepartmentViewSet(BaseModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filterset_fields = ['status']
    search_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).order_by('sort', 'id')
        top_depts = queryset.filter(parent__isnull=True)
        serializer = self.get_serializer(top_depts, many=True)
        return success_response(serializer.data)


class LoginLogViewSet(BaseModelViewSet):
    queryset = LoginLog.objects.all()
    serializer_class = LoginLogSerializer
    filterset_fields = ['status', 'username']
    search_fields = ['username', 'ip']
    ordering_fields = ['login_time']
