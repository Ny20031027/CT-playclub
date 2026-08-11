from django.db import transaction
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from rest_framework import serializers, viewsets
from rest_framework.decorators import action

from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeWallet,
    EmployeeContract, EmployeeStatus, EmployeeSkillRelation, SkillLevel,
    GameRank, EmployeeGameRank,
    SkillGameplay, GameplayPresetItem, GameplayDifficulty, GameplayLevelOption,
    GameplayService, GameplayPriceRule, ValueAddedService,
    AddonValueAddedService, ServiceValueAdded
)
from .serializers import (
    EmployeeSerializer, EmployeeSkillSerializer, EmployeeTagSerializer,
    EmployeeWalletSerializer, EmployeeContractSerializer,
    EmployeeStatusSerializer, EmployeeSkillRelationSerializer,
    EmployeeSimpleSerializer, GameRankSerializer, EmployeeGameRankSerializer
)
from .skill_services import sync_employee_rank_skills, sync_rank_auto_skill


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filterset_fields = ['status', 'level', 'gender', 'department', 'id_card_verified']
    search_fields = ['nickname', 'real_name', 'employee_no', 'phone']
    ordering_fields = ['sort', 'rating', 'order_count', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return success_response({'results': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='simple')
    def simple_list(self, request):
        employees = self.get_queryset().filter(status__in=['idle', 'busy']).order_by('sort')
        serializer = EmployeeSimpleSerializer(employees, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        employee = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(Employee._meta.get_field('status').flatchoices):
            employee.status = new_status
            employee.save(update_fields=['status', 'updated_at'])
            return success_response(msg='状态更新成功')
        return success_response(code=400, msg='无效的状态')

    @action(detail=True, methods=['post'], url_path='ban')
    def ban_employee(self, request, pk=None):
        """封禁打手（登录拦截）：duration_type=hours|days|forever"""
        employee = self.get_object()
        if not employee.user:
            return success_response(code=400, msg='该打手未绑定用户，无法封禁')
        from apps.account.ban_utils import apply_ban, ban_info
        try:
            apply_ban(
                employee.user,
                request.data.get('duration_type', 'forever'),
                request.data.get('duration'),
                request.data.get('reason', ''),
            )
        except ValueError as exc:
            return error_response(msg=str(exc))
        return success_response(ban_info(employee.user), msg='封禁成功，该用户已被强制下线')

    @action(detail=True, methods=['post'], url_path='unban')
    def unban_employee(self, request, pk=None):
        """解封打手"""
        employee = self.get_object()
        if employee.user:
            from apps.account.ban_utils import remove_ban
            remove_ban(employee.user)
        return success_response(msg='已解封')

    @action(detail=True, methods=['post'], url_path='freeze-commission')
    def freeze_commission(self, request, pk=None):
        """冻结/解冻打手佣金"""
        employee = self.get_object()
        frozen = request.data.get('frozen') is True or request.data.get('frozen') in (True, 'true', 1, '1')
        employee.commission_frozen = bool(frozen)
        employee.save(update_fields=['commission_frozen'])
        return success_response(msg='佣金已冻结' if frozen else '佣金已解冻')

    @action(detail=True, methods=['get'], url_path='skills')
    def employee_skills(self, request, pk=None):
        employee = self.get_object()
        relations = EmployeeSkillRelation.objects.filter(employee=employee)
        serializer = EmployeeSkillRelationSerializer(relations, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='add-skill')
    def add_skill(self, request, pk=None):
        employee = self.get_object()
        skill_id = request.data.get('skill_id')
        skill = EmployeeSkill.objects.filter(
            id=skill_id, assignment_mode='manual', status=True, is_deleted=False
        ).first()
        if not skill:
            raise serializers.ValidationError({'skill_id': '只能人工添加管理员授予类型的技能'})
        unit_price = self._manual_price(request.data.get('unit_price', skill.unit_price))
        relation = EmployeeSkillRelation.objects.filter(employee=employee, skill=skill).first()
        if relation:
            relation.unit_price = unit_price
            relation.assignment_source = 'manual'
            relation.price_overridden = True
            relation.is_deleted = False
            relation.save(update_fields=[
                'unit_price', 'assignment_source', 'price_overridden', 'is_deleted', 'updated_at'
            ])
        else:
            relation = EmployeeSkillRelation.objects.create(
                employee=employee, skill=skill, unit_price=unit_price,
                assignment_source='manual', price_overridden=True
            )
        return success_response(EmployeeSkillRelationSerializer(relation).data)

    @action(detail=True, methods=['post'], url_path='remove-skill')
    def remove_skill(self, request, pk=None):
        employee = self.get_object()
        skill_id = request.data.get('skill') or request.data.get('skill_id')
        EmployeeSkillRelation.objects.filter(
            employee=employee, skill_id=skill_id, assignment_source='manual'
        ).update(is_deleted=True)
        return success_response(msg='技能已移除')

    @staticmethod
    def _manual_price(value):
        try:
            price = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError({'unit_price': '专属价格格式不正确'})
        if price < 0:
            raise serializers.ValidationError({'unit_price': '专属价格不能小于0'})
        return price

    @action(detail=True, methods=['get', 'post'], url_path='skill-system')
    @transaction.atomic
    def skill_system(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'POST':
            previous_rank_categories = set(EmployeeGameRank.objects.filter(
                employee=employee, is_deleted=False
            ).values_list('game_category_id', flat=True))
            rank_data = request.data.get('ranks', [])
            manual_skill_data = request.data.get('manual_skills', [])
            if not isinstance(rank_data, list) or not isinstance(manual_skill_data, list):
                raise serializers.ValidationError('段位和技能配置必须为数组')

            desired_rank_categories = set()
            for item in rank_data:
                category_id = int(item.get('game_category_id') or 0)
                rank_id = int(item.get('rank_id') or 0)
                if not category_id or not rank_id:
                    continue
                rank = GameRank.objects.filter(
                    id=rank_id, game_category_id=category_id,
                    status=True, is_deleted=False
                ).first()
                if not rank:
                    raise serializers.ValidationError({'ranks': '存在无效或跨游戏分类的段位'})
                desired_rank_categories.add(category_id)
                relation = EmployeeGameRank.objects.filter(
                    employee=employee, game_category_id=category_id
                ).first()
                if relation:
                    relation.rank = rank
                    relation.is_deleted = False
                    relation.save(update_fields=['rank', 'is_deleted', 'updated_at'])
                else:
                    EmployeeGameRank.objects.create(
                        employee=employee, game_category_id=category_id, rank=rank
                    )
                employee.game_categories.add(category_id)

            EmployeeGameRank.objects.filter(
                employee=employee, is_deleted=False
            ).exclude(game_category_id__in=desired_rank_categories).update(is_deleted=True)

            desired_manual_ids = set()
            for item in manual_skill_data:
                skill_id = int(item.get('skill_id') or 0)
                skill = EmployeeSkill.objects.filter(
                    id=skill_id, assignment_mode='manual', status=True, is_deleted=False
                ).first()
                if not skill:
                    raise serializers.ValidationError({'manual_skills': '只能分配启用中的人工授予技能'})
                try:
                    unit_price = Decimal(str(item.get('unit_price')))
                except (InvalidOperation, TypeError, ValueError):
                    raise serializers.ValidationError({'manual_skills': '专属价格格式不正确'})
                if unit_price < 0:
                    raise serializers.ValidationError({'manual_skills': '专属价格不能小于0'})
                desired_manual_ids.add(skill_id)
                relation = EmployeeSkillRelation.objects.filter(
                    employee=employee, skill=skill
                ).first()
                if relation:
                    relation.unit_price = unit_price
                    relation.assignment_source = 'manual'
                    relation.price_overridden = True
                    relation.is_deleted = False
                    relation.save(update_fields=[
                        'unit_price', 'assignment_source', 'price_overridden',
                        'is_deleted', 'updated_at'
                    ])
                else:
                    EmployeeSkillRelation.objects.create(
                        employee=employee, skill=skill, unit_price=unit_price,
                        assignment_source='manual', price_overridden=True
                    )

            EmployeeSkillRelation.objects.filter(
                employee=employee, assignment_source='manual', is_deleted=False
            ).exclude(skill_id__in=desired_manual_ids).update(is_deleted=True)
            for category_id in previous_rank_categories | desired_rank_categories:
                sync_employee_rank_skills(employee, category_id)

        ranks = EmployeeGameRank.objects.filter(
            employee=employee, is_deleted=False
        ).select_related('game_category', 'rank').order_by('game_category__sort', 'rank__sort')
        relations = EmployeeSkillRelation.objects.filter(
            employee=employee, is_deleted=False
        ).select_related('skill', 'skill__game_category', 'skill__required_rank')
        return success_response({
            'ranks': EmployeeGameRankSerializer(ranks, many=True).data,
            'skills': EmployeeSkillRelationSerializer(relations, many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='convert')
    @transaction.atomic
    def convert_customer(self, request):
        """将客户转换为打手"""
        from apps.customer.models import Customer, CustomerService
        from apps.account.models import Role

        customer_id = request.data.get('customer_id')
        level_num = request.data.get('level_num', 0)
        game_category_ids = request.data.get('game_category_ids') or []

        if not customer_id:
            return success_response(code=400, msg='请选择客户')

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return success_response(code=400, msg='客户不存在')

        if not customer.user:
            return success_response(code=400, msg='该客户未关联用户账号')

        user = customer.user
        if Employee.objects.filter(user=user, is_deleted=False).exists():
            return success_response(code=400, msg='该用户已经是打手')

        restored = Employee.objects.filter(user=user, is_deleted=True).update(
            is_deleted=False,
            nickname=customer.nickname,
            phone=customer.phone,
            avatar=str(customer.avatar).strip(),
            gender=customer.gender,
            level_num=level_num,
            status='idle',
            online_status=False,
        )
        if restored:
            restored_emp = Employee.objects.filter(user=user, is_deleted=False).first()
            if restored_emp and game_category_ids:
                restored_emp.game_categories.set(game_category_ids)
            CustomerService.objects.filter(customer=customer, is_deleted=False).update(is_deleted=True)
            customer.delete()
            user.roles.remove(*user.roles.filter(code='customer'))
            dasher_role = Role.objects.filter(code='dasher', status=True, is_deleted=False).first()
            if dasher_role:
                user.roles.add(dasher_role)
            return success_response(msg='转换成功')

        import time
        employee_no = f'DS{int(time.time())}'
        employee = Employee.objects.create(
            user=user,
            employee_no=employee_no,
            real_name=customer.nickname or user.nickname or f'用户{user.id}',
            nickname=customer.nickname,
            phone=customer.phone,
            avatar=str(customer.avatar).strip(),
            gender=customer.gender,
            level_num=level_num,
            status='idle',
        )
        if game_category_ids:
            employee.game_categories.set(game_category_ids)
        CustomerService.objects.filter(customer=customer, is_deleted=False).update(is_deleted=True)
        customer.delete()
        user.roles.remove(*user.roles.filter(code='customer'))
        dasher_role = Role.objects.filter(code='dasher', status=True, is_deleted=False).first()
        if dasher_role:
            user.roles.add(dasher_role)
        return success_response(msg='转换成功')

    @action(detail=True, methods=['post'], url_path='remove')
    @transaction.atomic
    def remove_employee(self, request, pk=None):
        """移除打手，恢复为客户身份"""
        employee = self.get_object()
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        user = employee.user

        from apps.customer.models import Customer, CustomerService
        from apps.account.models import Role

        customer = Customer.objects.filter(user=user, is_deleted=False).first()
        if customer is None:
            customer = Customer.objects.filter(user=user, is_deleted=True).first()
            if customer:
                customer.is_deleted = False
                customer.save(update_fields=['is_deleted', 'updated_at'])
            else:
                customer = Customer.objects.create(
                    user=user,
                    nickname=employee.nickname or employee.real_name,
                    phone=employee.phone,
                    source='打手转客户',
                )

        customer.nickname = customer.nickname or employee.nickname or employee.real_name or user.nickname or user.username
        customer.phone = customer.phone or employee.phone or user.phone
        customer.avatar = str(customer.avatar).strip() or str(employee.avatar).strip() or str(user.avatar).strip()
        customer.gender = customer.gender or employee.gender or user.gender
        customer.status = True
        if not customer.source:
            customer.source = '打手转客户'
        customer.is_deleted = False
        customer.save()

        CustomerService.objects.filter(customer=customer, is_deleted=False).update(is_deleted=True)

        employee.status = 'offline'
        employee.online_status = False
        employee.is_deleted = True
        employee.save(update_fields=['status', 'online_status', 'is_deleted', 'updated_at'])

        user.roles.remove(*user.roles.filter(code='dasher'))
        customer_role = Role.objects.filter(code='customer', status=True, is_deleted=False).first()
        if customer_role:
            user.roles.add(customer_role)
        return success_response(msg='已恢复为客户身份')

    @action(detail=True, methods=['get'], url_path='wallet')
    def employee_wallet(self, request, pk=None):
        employee = self.get_object()
        wallet, _ = EmployeeWallet.objects.get_or_create(employee=employee)
        serializer = EmployeeWalletSerializer(wallet)
        return success_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='contracts')
    def employee_contracts(self, request, pk=None):
        employee = self.get_object()
        contracts = employee.contracts.all()
        serializer = EmployeeContractSerializer(contracts, many=True)
        return success_response(serializer.data)


class GameRankViewSet(BaseModelViewSet):
    queryset = GameRank.objects.select_related('game_category').all()
    serializer_class = GameRankSerializer
    filterset_fields = ['game_category', 'status']
    search_fields = ['name', 'game_category__name']
    ordering_fields = ['sort', 'id']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return success_response({'results': self.get_serializer(queryset, many=True).data})

    def perform_create(self, serializer):
        rank = serializer.save()
        self._sync_category(rank.game_category_id)

    def perform_update(self, serializer):
        old_category_id = serializer.instance.game_category_id
        rank = serializer.save()
        self._sync_category(old_category_id)
        if rank.game_category_id != old_category_id:
            self._sync_category(rank.game_category_id)

    def perform_destroy(self, instance):
        category_id = instance.game_category_id
        super().perform_destroy(instance)
        self._sync_category(category_id)

    @staticmethod
    def _sync_category(category_id):
        employee_ids = EmployeeGameRank.objects.filter(
            game_category_id=category_id, is_deleted=False
        ).values_list('employee_id', flat=True)
        for employee in Employee.objects.filter(id__in=employee_ids, is_deleted=False):
            sync_employee_rank_skills(employee, category_id)


class EmployeeSkillViewSet(BaseModelViewSet):
    queryset = EmployeeSkill.objects.select_related('game_category', 'required_rank').all()
    serializer_class = EmployeeSkillSerializer
    filterset_fields = ['status', 'category', 'game_category', 'assignment_mode', 'pricing_unit']
    search_fields = ['name', 'category']
    ordering_fields = ['sort', 'id']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return success_response({'results': serializer.data})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data)

    @staticmethod
    def _decimal(value, field_name):
        try:
            return Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError):
            raise serializers.ValidationError({field_name: '请输入有效数字'})

    def _sync_gameplays(self, skill, gameplays_data):
        if gameplays_data is None:
            return
        if not isinstance(gameplays_data, list):
            raise serializers.ValidationError({'gameplays': '玩法配置必须是数组'})

        names = [str(item.get('name', '')).strip() for item in gameplays_data]
        if any(not name for name in names):
            raise serializers.ValidationError({'gameplays': '玩法名称不能为空'})
        if len(names) != len(set(names)):
            raise serializers.ValidationError({'gameplays': '同一技能下玩法名称不能重复'})

        # 预先删除本次不再保留的玩法，避免重命名时与待删除记录的 (skill, name) 唯一键冲突
        keep_ids = set()
        keep_names = set()
        for index, item in enumerate(gameplays_data):
            gameplay_id = item.get('id')
            if gameplay_id:
                keep_ids.add(gameplay_id)
            else:
                keep_names.add(names[index])
        existing_gameplays = SkillGameplay.objects.filter(skill=skill)
        if keep_names:
            keep_ids.update(existing_gameplays.filter(name__in=keep_names).values_list('id', flat=True))
        if keep_ids:
            existing_gameplays.exclude(id__in=keep_ids).delete()
        else:
            existing_gameplays.delete()

        gameplay_fields = [
            'order_mode', 'name', 'description', 'display_image',
            'preset_content', 'preset_remark', 'preset_price',
            'difficulty_enabled', 'gender_limit',
            'companion_mode', 'settlement_unit', 'remark_required', 'sort', 'status'
        ]
        for index, item in enumerate(gameplays_data):
            order_mode = item.get('order_mode', 'custom')
            if order_mode not in ('custom', 'preset'):
                raise serializers.ValidationError({'order_mode': '不支持的下单模式'})

            gameplay_id = item.get('id')
            gameplay = None
            if gameplay_id:
                gameplay = SkillGameplay.objects.filter(id=gameplay_id, skill=skill).first()
                if gameplay is None:
                    raise serializers.ValidationError({'gameplays': f'玩法ID {gameplay_id} 不属于当前技能'})
            if gameplay is None:
                # id 未传或不可用时，按 (skill, name) 唯一键匹配现有玩法，避免重复创建
                gameplay = SkillGameplay.objects.filter(skill=skill, name=names[index]).first()
            if gameplay is None:
                gameplay = SkillGameplay(skill=skill)

            for field in gameplay_fields:
                if field in item:
                    setattr(gameplay, field, item[field])
            gameplay.order_mode = order_mode
            gameplay.name = names[index]
            gameplay.description = str(item.get('description', '') or '').strip()
            gameplay.display_image = str(item.get('display_image', '') or '').strip()
            gameplay.preset_content = str(item.get('preset_content', '') or '').strip()
            gameplay.preset_remark = str(item.get('preset_remark', '') or '').strip()
            gameplay.sort = item.get('sort', index)

            if order_mode == 'preset':
                preset_items = item.get('preset_items', [])
                if not isinstance(preset_items, list):
                    raise serializers.ValidationError({'preset_items': f'玩法“{gameplay.name}”的预制单必须是数组'})
                preset_names = [str(preset.get('name', '')).strip() for preset in preset_items]
                if any(not name for name in preset_names):
                    raise serializers.ValidationError({'preset_items': f'玩法“{gameplay.name}”存在未填写名称的预制单'})
                if len(preset_names) != len(set(preset_names)):
                    raise serializers.ValidationError({'preset_items': f'玩法“{gameplay.name}”下的预制单名称不能重复'})
                if gameplay.status and not preset_items:
                    raise serializers.ValidationError({'preset_items': f'玩法“{gameplay.name}”请至少添加一个预制单'})
                # 预制单不保留选配维度，避免后台隐藏后仍携带旧价格或规格。
                gameplay.difficulty_enabled = False
                gameplay.male_price_delta = Decimal('0')
                gameplay.female_price_delta = Decimal('0')
                gameplay.base_price = Decimal('0')
                gameplay.remark_required = False
                gameplay.save()
                GameplayDifficulty.objects.filter(gameplay=gameplay).delete()
                GameplayLevelOption.objects.filter(gameplay=gameplay).delete()
                GameplayService.objects.filter(gameplay=gameplay).delete()
                GameplayPriceRule.objects.filter(gameplay=gameplay).delete()
                ValueAddedService.objects.filter(gameplay=gameplay).delete()
                provided_preset_ids = [preset.get('id') for preset in preset_items if preset.get('id')]
                if len(provided_preset_ids) != len(set(provided_preset_ids)):
                    raise serializers.ValidationError({'preset_items': '预制单ID不能重复'})
                owned_preset_ids = set(GameplayPresetItem.objects.filter(
                    gameplay=gameplay, id__in=provided_preset_ids
                ).values_list('id', flat=True))
                if len(owned_preset_ids) != len(set(provided_preset_ids)):
                    raise serializers.ValidationError({'preset_items': '存在不属于当前玩法的预制单'})
                GameplayPresetItem.objects.filter(gameplay=gameplay).exclude(
                    id__in=provided_preset_ids
                ).delete()
                for existing_id in owned_preset_ids:
                    GameplayPresetItem.objects.filter(id=existing_id).update(name=f'__sync__{existing_id}')
                keep_preset_ids = []
                for preset_index, preset_data in enumerate(preset_items):
                    preset_id = preset_data.get('id')
                    preset = None
                    if preset_id:
                        preset = GameplayPresetItem.objects.filter(
                            id=preset_id, gameplay=gameplay
                        ).first()
                        if preset is None:
                            raise serializers.ValidationError({'preset_items': f'预制单ID {preset_id} 不属于当前玩法'})
                    if preset is None:
                        preset = GameplayPresetItem.objects.filter(
                            gameplay=gameplay, name=preset_names[preset_index]
                        ).first()
                    if preset is None:
                        preset = GameplayPresetItem(gameplay=gameplay)
                    preset.name = preset_names[preset_index]
                    preset.display_image = str(preset_data.get('display_image', '') or '').strip()
                    preset.content = str(preset_data.get('content', '') or '').strip()
                    preset.remark = str(preset_data.get('remark', '') or '').strip()
                    preset.price = self._decimal(preset_data.get('price', 0), 'preset_items.price')
                    try:
                        required_people = int(preset_data.get('required_people', 1) or 1)
                    except (TypeError, ValueError):
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”所需人数必须是整数'})
                    if required_people < 1:
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”所需人数最低为1'})
                    if required_people > 999:
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”所需人数不能超过999'})
                    preset.required_people = required_people
                    preset.sort = preset_data.get('sort', preset_index)
                    preset.status = preset_data.get('status', True) is not False
                    preset.is_deleted = False
                    if preset.price < 0:
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”价格不能小于0'})
                    if gameplay.status and preset.status and not preset.display_image:
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”请上传显示图片'})
                    if gameplay.status and preset.status and not preset.content:
                        raise serializers.ValidationError({'preset_items': f'预制单“{preset.name}”请填写项目内容'})
                    preset.save()
                    keep_preset_ids.append(preset.id)
                GameplayPresetItem.objects.filter(gameplay=gameplay).exclude(id__in=keep_preset_ids).delete()
                continue

            settlement_unit = item.get('settlement_unit', 'hour')
            gender_limit = {
                'male': 'male_only',
                'female': 'female_only',
            }.get(item.get('gender_limit', 'unlimited'), item.get('gender_limit', 'unlimited'))
            if gender_limit not in ('unlimited', 'male_only', 'female_only', 'optional'):
                raise serializers.ValidationError({'gender_limit': '不支持的服务者性别配置'})
            min_quantity = self._decimal(item.get('min_quantity', 1), 'min_quantity')
            quantity_step = self._decimal(item.get('quantity_step', 1), 'quantity_step')
            base_price = self._decimal(item.get('base_price', 0), 'base_price')
            male_price_delta = self._decimal(item.get('male_price_delta', 0), 'male_price_delta')
            female_price_delta = self._decimal(item.get('female_price_delta', 0), 'female_price_delta')

            if settlement_unit == 'hour':
                if min_quantity < Decimal('0.5'):
                    raise serializers.ValidationError({'min_quantity': '按小时结算最低为0.5小时'})
                if quantity_step < Decimal('0.5') or quantity_step % Decimal('0.5') != 0:
                    raise serializers.ValidationError({'quantity_step': '小时购买步长必须是0.5的倍数'})
            elif settlement_unit == 'round':
                if min_quantity < 1 or min_quantity % 1 != 0 or quantity_step < 1 or quantity_step % 1 != 0:
                    raise serializers.ValidationError({'min_quantity': '按局结算最低1局，且必须使用整数'})
            else:
                raise serializers.ValidationError({'settlement_unit': '不支持的结算单位'})

            gameplay.gender_limit = gender_limit
            gameplay.min_quantity = min_quantity
            gameplay.quantity_step = quantity_step
            gameplay.base_price = base_price
            gameplay.male_price_delta = male_price_delta
            gameplay.female_price_delta = female_price_delta
            gameplay.sort = item.get('sort', index)
            gameplay.save()
            GameplayPresetItem.objects.filter(gameplay=gameplay).delete()

            difficulties = item.get('difficulties', []) if gameplay.difficulty_enabled else []
            levels = item.get('levels', [])
            services = item.get('services', [])
            if gameplay.difficulty_enabled and not difficulties:
                raise serializers.ValidationError({'difficulties': f'玩法“{gameplay.name}”已启用难度，请至少添加一个难度'})
            if not levels:
                raise serializers.ValidationError({'levels': f'玩法“{gameplay.name}”请至少添加一个等级'})
            if not services:
                raise serializers.ValidationError({'services': f'玩法“{gameplay.name}”请至少添加一个服务'})

            service_names_set = set(str(row.get('name', '')).strip() for row in services)

            option_specs = [
                (GameplayDifficulty, difficulties, False, False),
                (GameplayLevelOption, levels, True, True),
                (GameplayService, services, True, False),
            ]
            for model, rows, has_description, has_allowed_services in option_specs:
                option_names = [str(row.get('name', '')).strip() for row in rows]
                if any(not name for name in option_names) or len(option_names) != len(set(option_names)):
                    raise serializers.ValidationError({'gameplays': f'玩法"{gameplay.name}"的选项名称为空或重复'})
                model.objects.filter(gameplay=gameplay).delete()
                for option_index, row in enumerate(rows):
                    values = {
                        'gameplay': gameplay,
                        'name': option_names[option_index],
                        'price_delta': self._decimal(row.get('price_delta', 0), 'price_delta'),
                        'sort': row.get('sort', option_index),
                        'status': row.get('status', True),
                    }
                    if has_description:
                        values['description'] = str(row.get('description', '')).strip()
                        values['is_recommended'] = row.get('is_recommended', False)
                    if has_allowed_services:
                        raw_services = row.get('allowed_services', []) or []
                        valid_services = [s for s in raw_services if s and s in service_names_set]
                        values['allowed_services'] = valid_services
                    model.objects.create(**values)

            difficulty_names = set(str(row.get('name', '')).strip() for row in difficulties)
            level_names = set(str(row.get('name', '')).strip() for row in levels)
            service_names = set(str(row.get('name', '')).strip() for row in services)
            GameplayPriceRule.objects.filter(gameplay=gameplay).delete()
            seen_rules = set()
            for row in item.get('price_rules', []):
                difficulty_name = str(row.get('difficulty_name', '')).strip() if gameplay.difficulty_enabled else ''
                level_name = str(row.get('level_name', '')).strip()
                service_name = str(row.get('service_name', '')).strip()
                gender_requirement = row.get('gender_requirement', 'any')
                if gender_requirement not in ('any', 'male', 'female'):
                    gender_requirement = 'any'
                companion_type = row.get('companion_type', 'single')
                if difficulty_name and difficulty_name not in difficulty_names:
                    raise serializers.ValidationError({'price_rules': f'价格规则引用了不存在的难度：{difficulty_name}'})
                if level_name and level_name not in level_names:
                    raise serializers.ValidationError({'price_rules': f'价格规则引用了不存在的等级：{level_name}'})
                if service_name and service_name not in service_names:
                    raise serializers.ValidationError({'price_rules': f'价格规则引用了不存在的服务：{service_name}'})
                if gameplay.companion_mode != 'both' and companion_type != gameplay.companion_mode:
                    raise serializers.ValidationError({'price_rules': '价格规则陪玩类型与玩法配置不一致'})
                key = (difficulty_name, level_name, service_name, gender_requirement, companion_type)
                if key in seen_rules:
                    raise serializers.ValidationError({'price_rules': '存在重复的组合价格规则'})
                seen_rules.add(key)
                GameplayPriceRule.objects.create(
                    gameplay=gameplay,
                    difficulty_name=difficulty_name,
                    level_name=level_name,
                    service_name=service_name,
                    gender_requirement=gender_requirement,
                    companion_type=companion_type,
                    unit_price=self._decimal(row.get('unit_price', 0), 'unit_price'),
                    status=row.get('status', True),
                )

            # 同步服务类型增值服务：每个服务类型独立设置
            for svc_row in services:
                svc_name = str(svc_row.get('name', '')).strip()
                svc_obj = GameplayService.objects.filter(gameplay=gameplay, name=svc_name).first()
                if not svc_obj:
                    continue
                svc_vas_data = svc_row.get('value_added_services', []) or []
                if not isinstance(svc_vas_data, list):
                    raise serializers.ValidationError({'value_added_services': '服务增值服务配置必须是数组'})
                ServiceValueAdded.objects.filter(service=svc_obj).delete()
                for vi, vr in enumerate(svc_vas_data):
                    v_name = str(vr.get('name', '')).strip()
                    if not v_name:
                        continue
                    ServiceValueAdded.objects.create(
                        service=svc_obj,
                        name=v_name,
                        description=str(vr.get('description', '') or '').strip(),
                        price=self._decimal(vr.get('price', 0), 'price'),
                        sort=int(vr.get('sort', vi) or vi),
                        status=vr.get('status', True),
                    )

            # 同步附加项目：管理员可选添加，客户可选非必选
            addon_data = item.get('value_added_services', [])
            if addon_data is None:
                addon_data = []
            if not isinstance(addon_data, list):
                raise serializers.ValidationError({'value_added_services': '增值服务配置必须是数组'})
            ValueAddedService.objects.filter(gameplay=gameplay).delete()
            for addon_index, addon_row in enumerate(addon_data):
                addon_name = str(addon_row.get('name', '')).strip()
                if not addon_name:
                    continue
                addon = ValueAddedService.objects.create(
                    gameplay=gameplay,
                    name=addon_name,
                    description=str(addon_row.get('description', '') or '').strip(),
                    price=self._decimal(addon_row.get('price', 0), 'price'),
                    sort=int(addon_row.get('sort', addon_index) or addon_index),
                    status=addon_row.get('status', True),
                )
                addon_values = addon_row.get('value_added_services', []) or []
                if not isinstance(addon_values, list):
                    raise serializers.ValidationError({
                        'value_added_services': f'附加项“{addon_name}”的附加增值配置必须是数组'
                    })
                addon_value_names = [str(row.get('name', '')).strip() for row in addon_values]
                non_empty_names = [name for name in addon_value_names if name]
                if len(non_empty_names) != len(set(non_empty_names)):
                    raise serializers.ValidationError({
                        'value_added_services': f'附加项“{addon_name}”存在重复的附加增值名称'
                    })
                for value_index, value_row in enumerate(addon_values):
                    value_name = addon_value_names[value_index]
                    if not value_name:
                        continue
                    AddonValueAddedService.objects.create(
                        addon=addon,
                        name=value_name,
                        description=str(value_row.get('description', '') or '').strip(),
                        price=self._decimal(value_row.get('price', 0), 'price'),
                        sort=int(value_row.get('sort', value_index) or value_index),
                        status=value_row.get('status', True),
                    )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        levels_data = request.data.get('levels', [])
        gameplays_data = request.data.get('gameplays', [])
        self_service_enabled = request.data.get('self_service_enabled', False)
        name = request.data.get('name', '')
        if name:
            EmployeeSkill.objects.filter(name=name, is_deleted=True).delete()

        if self_service_enabled and (not gameplays_data or len(gameplays_data) == 0):
            raise serializers.ValidationError({'gameplays': '启用自助下单时必须至少添加一个玩法'})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        skill = serializer.save()

        for i, lv in enumerate(levels_data):
            SkillLevel.objects.create(
                skill=skill,
                name=lv.get('name', ''),
                unit_price=lv.get('unit_price', 0),
                sort=lv.get('sort', i),
            )

        self._sync_gameplays(skill, gameplays_data)
        sync_rank_auto_skill(skill)

        return success_response(self.get_serializer(skill).data)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        affected_employee_ids = list(EmployeeSkillRelation.objects.filter(
            skill=instance, is_deleted=False
        ).values_list('employee_id', flat=True))
        levels_data = request.data.get('levels', None)
        gameplays_data = request.data.get('gameplays', None)
        self_service_enabled = request.data.get('self_service_enabled', instance.self_service_enabled)

        if self_service_enabled and gameplays_data is not None and len(gameplays_data) == 0:
            raise serializers.ValidationError({'gameplays': '启用自助下单时必须至少添加一个玩法'})
        if self_service_enabled and gameplays_data is None:
            existing_count = instance.self_service_gameplays.count()
            if existing_count == 0:
                raise serializers.ValidationError({'gameplays': '启用自助下单时必须至少添加一个玩法'})

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        skill = serializer.save()

        if levels_data is not None:
            SkillLevel.objects.filter(skill=skill).delete()
            for i, lv in enumerate(levels_data):
                SkillLevel.objects.create(
                    skill=skill,
                    name=lv.get('name', ''),
                    unit_price=lv.get('unit_price', 0),
                    sort=lv.get('sort', i),
                )

        self._sync_gameplays(skill, gameplays_data)
        for employee in Employee.objects.filter(id__in=affected_employee_ids, is_deleted=False):
            sync_employee_rank_skills(employee, skill.game_category_id)
        sync_rank_auto_skill(skill)

        return success_response(self.get_serializer(skill).data)


class EmployeeTagViewSet(BaseModelViewSet):
    queryset = EmployeeTag.objects.all()
    serializer_class = EmployeeTagSerializer
    filterset_fields = ['status']
    search_fields = ['name']
    ordering_fields = ['sort', 'id']


class EmployeeWalletViewSet(BaseModelViewSet):
    queryset = EmployeeWallet.objects.all()
    serializer_class = EmployeeWalletSerializer
    filterset_fields = []
    search_fields = ['employee__nickname']


class EmployeeContractViewSet(BaseModelViewSet):
    queryset = EmployeeContract.objects.all()
    serializer_class = EmployeeContractSerializer
    filterset_fields = ['status', 'contract_type', 'employee']
    search_fields = ['contract_no', 'employee__nickname']


class EmployeeStatusViewSet(BaseModelViewSet):
    queryset = EmployeeStatus.objects.all()
    serializer_class = EmployeeStatusSerializer
    filterset_fields = []
    search_fields = ['employee__nickname']
