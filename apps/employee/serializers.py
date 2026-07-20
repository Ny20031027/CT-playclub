from rest_framework import serializers
from .models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeWallet,
    EmployeeContract, EmployeeStatus, EmployeeSkillRelation, SkillLevel
)


class SkillLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillLevel
        fields = ['id', 'skill', 'name', 'unit_price', 'sort']
        read_only_fields = ['id']


class EmployeeSkillSerializer(serializers.ModelSerializer):
    game_category_id = serializers.IntegerField(source='game_category.id', read_only=True)
    game_category_name = serializers.CharField(source='game_category.name', read_only=True, default='')
    levels = SkillLevelSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeSkill
        fields = ['id', 'name', 'category', 'game_category', 'game_category_id', 'game_category_name',
                  'unit_price', 'icon', 'sort', 'status', 'levels', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmployeeTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeTag
        fields = ['id', 'name', 'color', 'sort', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmployeeSkillRelationSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_category = serializers.CharField(source='skill.category', read_only=True)
    level_name = serializers.CharField(source='skill_level.name', read_only=True, default='')

    class Meta:
        model = EmployeeSkillRelation
        fields = ['id', 'skill', 'skill_name', 'skill_category', 'skill_level', 'level_name', 'unit_price']
        read_only_fields = ['id']


class EmployeeWalletSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = EmployeeWallet
        fields = ['id', 'employee', 'employee_name', 'balance', 'frozen_amount',
                  'total_income', 'total_withdraw', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeContractSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = EmployeeContract
        fields = ['id', 'employee', 'employee_name', 'contract_no', 'contract_type',
                  'start_date', 'end_date', 'status', 'file', 'salary_type',
                  'base_salary', 'commission_rate', 'remark', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmployeeStatusSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = EmployeeStatus
        fields = ['id', 'employee', 'employee_name', 'last_active', 'last_order_time',
                  'today_orders', 'today_duration', 'today_income', 'device', 'login_ip']
        read_only_fields = ['id']


class EmployeeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    password = serializers.CharField(write_only=True, required=False)
    department_name = serializers.CharField(source='department.name', read_only=True)
    tag_names = serializers.SerializerMethodField()
    skill_list = serializers.SerializerMethodField()
    wallet = EmployeeWalletSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'user', 'username', 'password', 'employee_no', 'real_name', 'nickname',
                  'phone', 'avatar', 'gender', 'age', 'birthday', 'id_card',
                  'id_card_verified', 'department', 'department_name', 'level', 'level_num', 'status',
                  'online_status', 'skills', 'tags', 'tag_names', 'skill_list',
                  'intro', 'rating', 'order_count', 'total_duration', 'join_date',
                  'bank_name', 'bank_card', 'alipay', 'wechat', 'qq', 'sort', 'remark',
                  'wallet', 'created_at', 'updated_at']
        read_only_fields = ['id', 'rating', 'order_count', 'total_duration',
                            'online_status', 'created_at', 'updated_at', 'user', 'username']
        extra_kwargs = {
            'employee_no': {'required': False},
            'real_name': {'required': False},
        }

    def get_tag_names(self, obj):
        return list(obj.tags.filter(status=True).values_list('name', flat=True))

    def get_skill_list(self, obj):
        relations = EmployeeSkillRelation.objects.filter(employee=obj, is_deleted=False)
        return EmployeeSkillRelationSerializer(relations, many=True).data

    def create(self, validated_data):
        # pop password before it reaches Employee.objects.create
        password = validated_data.pop('password', None)
        skills = validated_data.pop('skills', [])
        tags = validated_data.pop('tags', [])

        # If no user provided, create one from request data
        request = self.context.get('request')
        if 'user' not in validated_data and request:
            username = request.data.get('username')
            if username:
                from apps.account.models import User
                user = User.objects.create_user(
                    username=username,
                    password=password or '123456',
                )
                validated_data['user'] = user

        # Auto-generate employee_no if not provided
        if not validated_data.get('employee_no'):
            import uuid
            validated_data['employee_no'] = 'EMP' + uuid.uuid4().hex[:8].upper()

        # Set real_name from nickname if not provided
        if not validated_data.get('real_name'):
            validated_data['real_name'] = validated_data.get('nickname', '')

        employee = Employee.objects.create(**validated_data)
        if tags:
            employee.tags.set(tags)
        EmployeeWallet.objects.get_or_create(employee=employee)
        EmployeeStatus.objects.get_or_create(employee=employee)
        return employee

    def update(self, instance, validated_data):
        tags = validated_data.pop('tags', None)
        skills = validated_data.pop('skills', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        return instance


class EmployeeSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['id', 'nickname', 'avatar', 'level', 'status', 'rating']
        read_only_fields = fields
