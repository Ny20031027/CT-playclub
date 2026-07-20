from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Role, Permission, Department, LoginLog
import requests


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError('用户名或密码错误')
        if not user.is_active:
            raise serializers.ValidationError('账号已被禁用')

        refresh = RefreshToken.for_user(user)
        attrs['user'] = user
        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)
        return attrs


class WxLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, help_text='wx.login()返回的code')

    def get_openid(self, code):
        """通过code获取openid"""
        # 微信小程序配置
        appid = 'wxc61625fcffa21deb'  # 从project.config.json获取
        secret = 'YOUR_APP_SECRET'  # 需要在微信公众平台获取
        url = f'https://api.weixin.qq.com/sns/jscode2session?appid={appid}&secret={secret}&js_code={code}&grant_type=authorization_code'
        
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            if 'openid' in data:
                return data['openid']
            else:
                raise serializers.ValidationError(f'微信登录失败: {data.get("errmsg", "未知错误")}')
        except Exception as e:
            raise serializers.ValidationError(f'微信登录失败: {str(e)}')

    def validate(self, attrs):
        code = attrs.get('code')
        
        # 获取openid
        openid = self.get_openid(code)
        
        # 查找或创建用户
        try:
            user = User.objects.get(wx_openid=openid)
        except User.DoesNotExist:
            # 创建新用户
            user = User.objects.create(
                username=f'wx_{openid[:8]}',
                wx_openid=openid,
                nickname=f'微信用户{openid[:6]}',
                is_active=True,
            )
        
        if not user.is_active:
            raise serializers.ValidationError('账号已被禁用')

        # 生成token
        refresh = RefreshToken.for_user(user)
        attrs['user'] = user
        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)
        return attrs


class UserInfoSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()
    customer_id = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'email', 'phone', 'avatar',
                  'gender', 'is_active', 'is_online', 'department', 'department_name',
                  'roles', 'permissions', 'user_type', 'customer_id', 'employee_id',
                  'is_superuser', 'last_login', 'last_login_ip', 'created_at']
        read_only_fields = ['id', 'username', 'last_login', 'last_login_ip', 'created_at']

    def get_roles(self, obj):
        return list(obj.roles.filter(status=True).values_list('code', flat=True))

    def get_permissions(self, obj):
        return list(obj.get_user_permissions())

    def get_user_type(self, obj):
        return obj.get_primary_identity_code()

    def get_customer_id(self, obj):
        try:
            return obj.customer.id
        except Exception:
            return None

    def get_employee_id(self, obj):
        try:
            return obj.employee.id
        except Exception:
            return None


class UserSerializer(serializers.ModelSerializer):
    role_names = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'nickname', 'email', 'phone', 'avatar',
                  'gender', 'is_active', 'is_online', 'department', 'department_name',
                  'roles', 'role_names', 'user_type', 'is_superuser',
                  'last_login', 'last_login_ip', 'created_at', 'updated_at']
        read_only_fields = ['id', 'last_login', 'last_login_ip', 'created_at', 'updated_at']
        extra_kwargs = {'password': {'write_only': True, 'required': False}}

    def get_role_names(self, obj):
        return list(obj.roles.filter(status=True).values_list('name', flat=True))

    def get_user_type(self, obj):
        return obj.get_primary_identity_code()

    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_password('123456')
        user.save()
        if roles:
            user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        roles = validated_data.pop('roles', None)
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


class RoleSerializer(serializers.ModelSerializer):
    permission_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'name', 'code', 'sort', 'status', 'remark', 'data_scope',
                  'permissions', 'permission_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_permission_count(self, obj):
        return obj.permissions.count()


class PermissionSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ['id', 'name', 'code', 'type', 'parent', 'path', 'component',
                  'icon', 'sort', 'visible', 'status', 'remark', 'children']
        read_only_fields = ['id', 'children']

    def get_children(self, obj):
        children = obj.children.filter(status=True, is_deleted=False).order_by('sort', 'id')
        return PermissionSerializer(children, many=True).data


class DepartmentSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'parent', 'sort', 'status', 'remark', 'children']
        read_only_fields = ['id', 'children']

    def get_children(self, obj):
        children = obj.children.filter(status=True, is_deleted=False).order_by('sort', 'id')
        return DepartmentSerializer(children, many=True).data


class LoginLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginLog
        fields = ['id', 'username', 'ip', 'user_agent', 'status', 'message', 'login_time']
        read_only_fields = fields
