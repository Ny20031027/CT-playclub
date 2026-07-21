from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action

from apps.common.response import success_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Employee, EmployeeSkill, EmployeeTag, EmployeeWallet,
    EmployeeContract, EmployeeStatus, EmployeeSkillRelation, SkillLevel
)
from .serializers import (
    EmployeeSerializer, EmployeeSkillSerializer, EmployeeTagSerializer,
    EmployeeWalletSerializer, EmployeeContractSerializer,
    EmployeeStatusSerializer, EmployeeSkillRelationSerializer,
    EmployeeSimpleSerializer
)


class EmployeeViewSet(BaseModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filterset_fields = ['status', 'level', 'gender', 'department', 'id_card_verified']
    search_fields = ['nickname', 'real_name', 'employee_no', 'phone']
    ordering_fields = ['sort', 'rating', 'order_count', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset

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
        level = request.data.get('level', '')
        unit_price = request.data.get('unit_price', 0)
        relation, created = EmployeeSkillRelation.objects.get_or_create(
            employee=employee,
            skill_id=skill_id,
            defaults={'level': level, 'unit_price': unit_price}
        )
        if not created:
            relation.level = level
            relation.unit_price = unit_price
            relation.save()
        return success_response(EmployeeSkillRelationSerializer(relation).data)

    @action(detail=True, methods=['post'], url_path='remove-skill')
    def remove_skill(self, request, pk=None):
        employee = self.get_object()
        skill_id = request.data.get('skill')
        EmployeeSkillRelation.objects.filter(employee=employee, skill_id=skill_id).delete()
        return success_response(msg='技能已移除')

    @action(detail=False, methods=['post'], url_path='convert')
    def convert_customer(self, request):
        """将客户转换为打手"""
        from apps.customer.models import Customer

        customer_id = request.data.get('customer_id')
        level_num = request.data.get('level_num', 0)

        if not customer_id:
            return success_response(code=400, msg='请选择客户')

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return success_response(code=400, msg='客户不存在')

        if not customer.user:
            return success_response(code=400, msg='该客户未关联用户账号')

        user = customer.user
        if Employee.objects.filter(user=user).exists():
            return success_response(code=400, msg='该用户已经是打手')

        import time
        employee_no = f'DS{int(time.time())}'
        Employee.objects.create(
            user=user,
            employee_no=employee_no,
            real_name=customer.nickname or user.nickname or f'用户{user.id}',
            nickname=customer.nickname,
            phone=customer.phone,
            level_num=level_num,
            status='idle',
        )
        customer.hard_delete()
        return success_response(msg='转换成功')

    @action(detail=True, methods=['post'], url_path='remove')
    def remove_employee(self, request, pk=None):
        """移除打手，恢复为客户身份"""
        employee = self.get_object()
        user = employee.user

        from apps.customer.models import Customer, CustomerService

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

        CustomerService.objects.filter(customer=customer).delete()
        employee.hard_delete()
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


class EmployeeSkillViewSet(BaseModelViewSet):
    queryset = EmployeeSkill.objects.all()
    serializer_class = EmployeeSkillSerializer
    filterset_fields = ['status', 'category']
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

    def create(self, request, *args, **kwargs):
        levels_data = request.data.get('levels', [])
        name = request.data.get('name', '')
        if name:
            EmployeeSkill.objects.filter(name=name, is_deleted=True).delete()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        skill = serializer.save()

        for i, lv in enumerate(levels_data):
            SkillLevel.objects.create(
                skill=skill,
                name=lv.get('name', ''),
                price_min=lv.get('price_min', 0),
                price_max=lv.get('price_max', 0),
                sort=lv.get('sort', i),
            )

        return success_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        levels_data = request.data.get('levels', None)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        skill = serializer.save()

        if levels_data is not None:
            SkillLevel.objects.filter(skill=skill).delete()
            for i, lv in enumerate(levels_data):
                SkillLevel.objects.create(
                    skill=skill,
                    name=lv.get('name', ''),
                    price_min=lv.get('price_min', 0),
                    price_max=lv.get('price_max', 0),
                    sort=lv.get('sort', i),
                )

        return success_response(serializer.data)


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
