from rest_framework import serializers
from apps.common.media import build_media_url
from apps.wx.models import GameCategory
from .models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeWallet,
    EmployeeContract, EmployeeStatus, EmployeeSkillRelation, SkillLevel,
    SkillGameplay, GameplayDifficulty, GameplayLevelOption,
    GameplayService, GameplayPriceRule
)


class SkillLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillLevel
        fields = ['id', 'skill', 'name', 'unit_price', 'sort']
        read_only_fields = ['id']


class GameplayOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=200, required=False, allow_blank=True)
    price_delta = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    sort = serializers.IntegerField(default=0)
    status = serializers.BooleanField(default=True)


class GameplayPriceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameplayPriceRule
        fields = [
            'id', 'difficulty_name', 'level_name', 'service_name',
            'gender_requirement', 'companion_type', 'unit_price', 'status'
        ]


class SkillGameplaySerializer(serializers.ModelSerializer):
    difficulties = serializers.SerializerMethodField()
    levels = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    price_rules = GameplayPriceRuleSerializer(many=True, read_only=True)

    class Meta:
        model = SkillGameplay
        fields = [
            'id', 'name', 'description', 'difficulty_enabled', 'gender_limit',
            'male_price_delta', 'female_price_delta',
            'companion_mode', 'settlement_unit', 'min_quantity', 'quantity_step',
            'base_price', 'remark_required', 'sort', 'status', 'difficulties',
            'levels', 'services', 'price_rules'
        ]

    @staticmethod
    def _options(queryset, include_description=False):
        values = []
        for item in queryset.filter(is_deleted=False).order_by('sort', 'id'):
            row = {
                'id': item.id,
                'name': item.name,
                'price_delta': item.price_delta,
                'is_recommended': getattr(item, 'is_recommended', False),
                'sort': item.sort,
                'status': item.status,
            }
            if include_description:
                row['description'] = item.description
                row['allowed_services'] = list(getattr(item, 'allowed_services', None) or [])
            values.append(row)
        return values

    def get_difficulties(self, obj):
        return self._options(obj.difficulties)

    def get_levels(self, obj):
        return self._options(obj.level_options, include_description=True)

    def get_services(self, obj):
        return self._options(obj.services, include_description=True)


class EmployeeSkillSerializer(serializers.ModelSerializer):
    game_category = serializers.PrimaryKeyRelatedField(
        queryset=GameCategory.objects.all(), required=False, allow_null=True
    )
    game_category_id = serializers.IntegerField(source='game_category.id', read_only=True)
    game_category_name = serializers.CharField(source='game_category.name', read_only=True, default='')
    levels = SkillLevelSerializer(many=True, read_only=True)
    gameplays = SkillGameplaySerializer(source='self_service_gameplays', many=True, read_only=True)

    class Meta:
        model = EmployeeSkill
        fields = ['id', 'name', 'category', 'game_category', 'game_category_id', 'game_category_name',
                  'unit_price', 'icon', 'sort', 'status', 'skill_type', 'min_people',
                  'description', 'trial_mode', 'order_notice', 'remark_placeholder',
                  'self_service_enabled', 'levels', 'gameplays', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # Sync category field from game_category name for backwards compatibility
        game_category = validated_data.get('game_category')
        if game_category:
            validated_data['category'] = game_category.name
        elif not validated_data.get('category'):
            validated_data['category'] = ''
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Sync category field from game_category name for backwards compatibility
        if 'game_category' in validated_data:
            game_category = validated_data['game_category']
            if game_category:
                validated_data['category'] = game_category.name
            elif validated_data['game_category'] is None:
                # Allow clearing the game_category association; keep existing category or empty it
                pass
        return super().update(instance, validated_data)


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
    avatar_url = serializers.SerializerMethodField()
    wallet = EmployeeWalletSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'user', 'username', 'password', 'employee_no', 'real_name', 'nickname',
                  'phone', 'avatar', 'avatar_url', 'gender', 'age', 'birthday', 'id_card',
                  'id_card_verified', 'department', 'department_name', 'level', 'level_num', 'status',
                  'online_status', 'work_status', 'skills', 'tags', 'tag_names', 'skill_list',
                  'intro', 'rating', 'order_count', 'total_duration', 'join_date',
                  'bank_name', 'bank_card', 'alipay', 'wechat', 'qq', 'sort', 'remark',
                  'wallet', 'created_at', 'updated_at']
        read_only_fields = ['id', 'rating', 'order_count', 'total_duration',
                            'online_status', 'created_at', 'updated_at', 'user', 'username', 'avatar_url']
        extra_kwargs = {
            'employee_no': {'required': False},
            'real_name': {'required': False},
        }

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))

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
        
        # 删除该用户的 Customer 记录，确保每个用户只存在于一张表
        if employee.user:
            from apps.customer.models import Customer
            Customer.objects.filter(user=employee.user, is_deleted=False).update(is_deleted=True)
        
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
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ['id', 'nickname', 'avatar', 'avatar_url', 'level', 'status', 'rating']
        read_only_fields = fields

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))
