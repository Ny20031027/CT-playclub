from rest_framework import serializers
from django.db import transaction
from apps.account.models import User
from apps.account.serializers import validate_display_id
from apps.common.media import build_media_url
from apps.wx.models import GameCategory
from .models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeWallet,
    EmployeeContract, EmployeeStatus, EmployeeSkillRelation, SkillLevel,
    GameRank, EmployeeGameRank,
    SkillGameplay, GameplayPresetItem, GameplayDifficulty, GameplayLevelOption,
    GameplayService, GameplayPriceRule, ValueAddedService,
    AddonValueAddedService, ServiceValueAdded, EmployeeArchiveRecord
)


class GameRankSerializer(serializers.ModelSerializer):
    game_category_name = serializers.CharField(source='game_category.name', read_only=True)

    class Meta:
        model = GameRank
        fields = ['id', 'game_category', 'game_category_name', 'name', 'sort', 'status']
        read_only_fields = ['id']


class EmployeeGameRankSerializer(serializers.ModelSerializer):
    game_category_name = serializers.CharField(source='game_category.name', read_only=True)
    rank_name = serializers.CharField(source='rank.name', read_only=True)

    class Meta:
        model = EmployeeGameRank
        fields = ['id', 'employee', 'game_category', 'game_category_name', 'rank', 'rank_name']
        read_only_fields = ['id']


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


class GameplayPresetItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameplayPresetItem
        fields = ['id', 'name', 'display_image', 'content', 'remark', 'price', 'required_people', 'sort', 'status']


class SkillGameplaySerializer(serializers.ModelSerializer):
    difficulties = serializers.SerializerMethodField()
    levels = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    price_rules = GameplayPriceRuleSerializer(many=True, read_only=True)
    value_added_services = serializers.SerializerMethodField()
    preset_items = GameplayPresetItemSerializer(many=True, read_only=True)

    class Meta:
        model = SkillGameplay
        fields = [
            'id', 'order_mode', 'name', 'description', 'display_image',
            'service_section_desc', 'addon_section_desc', 'more_service_section_desc',
            'preset_content', 'preset_remark', 'preset_price', 'preset_items',
            'difficulty_enabled', 'gender_limit',
            'male_price_delta', 'female_price_delta',
            'companion_mode', 'settlement_unit', 'min_quantity', 'quantity_step',
            'base_price', 'remark_required', 'sort', 'status', 'difficulties',
            'levels', 'services', 'price_rules', 'value_added_services'
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
        services = self._options(obj.services, include_description=True)
        # 为每个服务类型挂载其独立的增值服务
        for svc in services:
            svc_id = svc['id']
            svc['value_added_services'] = [
                {
                    'id': v.id,
                    'name': v.name,
                    'description': v.description or '',
                    'price': v.price,
                    'sort': v.sort,
                }
                for v in ServiceValueAdded.objects.filter(
                    service_id=svc_id, status=True, is_deleted=False
                ).order_by('sort', 'id')
            ]
        return services

    def get_value_added_services(self, obj):
        qs = ValueAddedService.objects.filter(
            gameplay_id=obj.id, is_deleted=False
        ).order_by('sort', 'id')
        return [{
            'id': item.id,
            'name': item.name,
            'description': item.description or '',
            'price': item.price,
            'sort': item.sort,
            'status': item.status,
            'value_added_services': [
                {
                    'id': value.id,
                    'name': value.name,
                    'description': value.description or '',
                    'price': value.price,
                    'sort': value.sort,
                    'status': value.status,
                }
                for value in AddonValueAddedService.objects.filter(
                    addon=item, is_deleted=False
                ).order_by('sort', 'id')
            ],
        } for item in qs]


class EmployeeSkillSerializer(serializers.ModelSerializer):
    game_category = serializers.PrimaryKeyRelatedField(
        queryset=GameCategory.objects.all(), required=False, allow_null=True
    )
    game_category_id = serializers.IntegerField(source='game_category.id', read_only=True)
    game_category_name = serializers.CharField(source='game_category.name', read_only=True, default='')
    required_rank_name = serializers.CharField(source='required_rank.name', read_only=True, default='')
    levels = SkillLevelSerializer(many=True, read_only=True)
    gameplays = SkillGameplaySerializer(source='self_service_gameplays', many=True, read_only=True)

    class Meta:
        model = EmployeeSkill
        fields = ['id', 'name', 'category', 'game_category', 'game_category_id', 'game_category_name',
                  'unit_price', 'pricing_unit', 'icon', 'sort', 'status', 'skill_type', 'min_people',
                  'required_rank', 'required_rank_name', 'assignment_mode',
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

    def validate(self, attrs):
        game_category = attrs.get('game_category', getattr(self.instance, 'game_category', None))
        required_rank = attrs.get('required_rank', getattr(self.instance, 'required_rank', None))
        assignment_mode = attrs.get('assignment_mode', getattr(self.instance, 'assignment_mode', 'manual'))
        if not game_category:
            raise serializers.ValidationError({'game_category': '请选择游戏分类'})
        if assignment_mode == 'rank_auto' and not required_rank:
            raise serializers.ValidationError({'required_rank': '请选择该游戏分类下的所需段位'})
        if required_rank and required_rank.game_category_id != game_category.id:
            raise serializers.ValidationError({'required_rank': '所需段位不属于所选游戏分类'})
        return attrs

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
    game_category_name = serializers.CharField(source='skill.game_category.name', read_only=True, default='')
    required_rank_name = serializers.CharField(source='skill.required_rank.name', read_only=True, default='')
    pricing_unit = serializers.CharField(source='skill.pricing_unit', read_only=True)
    icon = serializers.CharField(source='skill.icon', read_only=True)

    class Meta:
        model = EmployeeSkillRelation
        fields = [
            'id', 'skill', 'skill_name', 'skill_category', 'skill_level', 'level_name',
            'game_category_name', 'required_rank_name', 'pricing_unit', 'icon', 'unit_price',
            'assignment_source', 'price_overridden', 'is_enabled'
        ]
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


class EmployeeArchiveRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    employee_real_name = serializers.CharField(source='employee.real_name', read_only=True)
    employee_phone = serializers.CharField(source='employee.phone', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    priority_text = serializers.CharField(source='get_priority_display', read_only=True)

    class Meta:
        model = EmployeeArchiveRecord
        fields = [
            'id', 'employee', 'employee_name', 'employee_real_name',
            'employee_phone', 'title', 'category', 'priority', 'priority_text',
            'content', 'next_follow_time', 'operator', 'operator_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'operator', 'operator_name', 'created_at', 'updated_at']


class EmployeeStatusSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = EmployeeStatus
        fields = ['id', 'employee', 'employee_name', 'last_active', 'last_order_time',
                  'today_orders', 'today_duration', 'today_income', 'device', 'login_ip']
        read_only_fields = ['id']


class EmployeeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    display_id = serializers.SerializerMethodField()
    edit_display_id = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    department_name = serializers.CharField(source='department.name', read_only=True)
    tag_names = serializers.SerializerMethodField()
    skill_list = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    voice_intro_url = serializers.SerializerMethodField()
    wallet = EmployeeWalletSerializer(read_only=True)
    game_category_ids = serializers.PrimaryKeyRelatedField(
        source='game_categories', many=True, required=False, allow_null=True,
        queryset=GameCategory.objects.all(), write_only=True
    )
    game_categories_list = serializers.SerializerMethodField(read_only=True)
    star_sort = serializers.IntegerField(required=False, min_value=0)
    commission_frozen = serializers.BooleanField(read_only=True)
    user_banned = serializers.SerializerMethodField()
    ban_detail = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ['id', 'user', 'username', 'display_id', 'edit_display_id', 'password', 'employee_no', 'real_name', 'nickname',
                  'phone', 'avatar', 'avatar_url', 'gender', 'age', 'birthday', 'id_card',
                  'id_card_verified', 'department', 'department_name', 'level', 'level_num', 'status',
                  'assessment_mode', 'online_status', 'work_status', 'skills', 'game_category_ids',
                  'game_categories_list', 'tags', 'tag_names', 'skill_list',
                  'intro', 'quick_welcome_message', 'quick_welcome_messages', 'voice_intro', 'voice_intro_url', 'voice_duration', 'rating', 'order_count', 'total_duration', 'fans_count',
                  'commission_balance', 'commission_frozen', 'platform_commission_rate', 'join_date',
                  'bank_name', 'bank_card', 'alipay', 'wechat', 'qq', 'sort', 'remark',
                  'is_star', 'star_sort', 'user_banned', 'ban_detail',
                  'wallet', 'created_at', 'updated_at']
        read_only_fields = ['id', 'rating', 'order_count', 'total_duration',
                            'online_status', 'created_at', 'updated_at', 'user', 'username', 'avatar_url',
                            'game_categories_list']
        extra_kwargs = {
            'employee_no': {'required': False},
            'real_name': {'required': False},
        }

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))

    def get_voice_intro_url(self, obj):
        return build_media_url(obj.voice_intro, self.context.get('request')) if obj.voice_intro else ''

    def get_tag_names(self, obj):
        return list(obj.tags.filter(status=True).values_list('name', flat=True))

    def get_display_id(self, obj):
        try:
            return obj.user.display_id
        except Exception:
            return ''

    def get_user_banned(self, obj):
        try:
            return bool(obj.user and obj.user.is_banned_active())
        except Exception:
            return False

    def get_ban_detail(self, obj):
        if not obj.user_id:
            return {'is_banned': False}
        from apps.account.ban_utils import ban_info
        return ban_info(obj.user)

    def validate_edit_display_id(self, value):
        value = validate_display_id(value)
        if not value:
            raise serializers.ValidationError('黑金ID不能为空')
        queryset = User.objects.filter(display_id=value)
        if self.instance and self.instance.user_id:
            queryset = queryset.exclude(pk=self.instance.user_id)
        if queryset.exists():
            raise serializers.ValidationError('该黑金ID已被其他用户使用')
        return value

    def get_game_categories_list(self, obj):
        return [{
            'id': gc.id,
            'name': gc.name,
            'icon': gc.icon or '',
        } for gc in obj.game_categories.filter(status=True).order_by('sort', 'id')]

    def get_skill_list(self, obj):
        relations = EmployeeSkillRelation.objects.filter(employee=obj, is_deleted=False)
        return EmployeeSkillRelationSerializer(relations, many=True).data

    def create(self, validated_data):
        display_id_val = validated_data.pop('edit_display_id', None)
        # pop password before it reaches Employee.objects.create
        password = validated_data.pop('password', None)
        skills = validated_data.pop('skills', [])
        tags = validated_data.pop('tags', [])
        game_categories = validated_data.pop('game_categories', [])

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
                user.ensure_display_id()
                validated_data['user'] = user

        if display_id_val and validated_data.get('user'):
            validated_data['user'].display_id = display_id_val
            validated_data['user'].save(update_fields=['display_id'])

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
        if game_categories:
            employee.game_categories.set(game_categories)
        EmployeeWallet.objects.get_or_create(
            employee=employee,
            defaults={'balance': employee.commission_balance},
        )
        EmployeeStatus.objects.get_or_create(employee=employee)
        
        # 删除该用户的 Customer 记录，确保每个用户只存在于一张表
        if employee.user:
            from apps.customer.models import Customer
            Customer.objects.filter(user=employee.user, is_deleted=False).update(is_deleted=True)
        
        return employee

    @transaction.atomic
    def update(self, instance, validated_data):
        display_id_val = validated_data.pop('edit_display_id', None)
        tags = validated_data.pop('tags', None)
        skills = validated_data.pop('skills', None)
        game_categories = validated_data.pop('game_categories', None)
        commission_balance = validated_data.get('commission_balance')
        wallet = None
        if commission_balance is not None:
            wallet, _ = EmployeeWallet.objects.select_for_update().get_or_create(
                employee=instance
            )
            if commission_balance < wallet.frozen_amount:
                raise serializers.ValidationError({
                    'commission_balance': '佣金余额不能低于当前冻结中的提现金额'
                })
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        if game_categories is not None:
            instance.game_categories.set(game_categories)
        if display_id_val and instance.user:
            instance.user.display_id = display_id_val
            instance.user.save(update_fields=['display_id'])
        if wallet is not None:
            wallet.balance = commission_balance
            wallet.save(update_fields=['balance', 'updated_at'])
        return instance


class EmployeeSimpleSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    display_id = serializers.CharField(source='user.display_id', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'display_id', 'nickname', 'avatar', 'avatar_url', 'level', 'status', 'rating']
        read_only_fields = fields

    def get_avatar_url(self, obj):
        return build_media_url(obj.avatar, self.context.get('request'))
