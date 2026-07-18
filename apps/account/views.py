from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
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
        user.save(update_fields=['is_online', 'last_login_ip'])

        data = {
            'token': serializer.validated_data['access'],
            'refresh': serializer.validated_data['refresh'],
            'user_info': UserInfoSerializer(user).data
        }
        return success_response(data)

    @action(detail=False, methods=['post'], url_path='wx-login')
    def wx_login(self, request):
        """微信小程序登录"""
        serializer = WxLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

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
        password = request.data.get('password', '123456')
        user.set_password(password)
        user.save()
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
