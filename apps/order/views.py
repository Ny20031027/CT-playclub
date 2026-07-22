from rest_framework import viewsets, status
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .comment_utils import create_order_comment_with_retry
from .models import (
    Order, OrderMember, OrderPrice, OrderComment, OrderRefund, OrderStatus
)
from .serializers import (
    OrderSerializer, OrderCreateSerializer, OrderMemberSerializer,
    OrderPriceSerializer, OrderCommentSerializer, OrderRefundSerializer
)


class OrderViewSet(BaseModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filterset_fields = ['status', 'order_type', 'pay_method', 'platform', 'customer', 'skill']
    search_fields = ['order_no', 'customer__nickname', 'game_id', 'game_name']
    ordering_fields = ['created_at', 'pay_amount', 'start_time']

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        order = self.get_object()
        if order.status != OrderStatus.PENDING_PAYMENT:
            return error_response(msg='订单状态不正确')
        pay_method = request.data.get('pay_method', 'balance')
        order.pay_method = pay_method
        order.pay_time = timezone.now()
        order.status = OrderStatus.PENDING_ASSIGN
        order.save()
        return success_response(msg='支付成功')

    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, pk=None):
        order = self.get_object()
        if order.status not in [OrderStatus.PENDING_ASSIGN, OrderStatus.PENDING_PAYMENT]:
            return error_response(msg='订单状态不正确，无法派单')
        employee_ids = request.data.get('employee_ids', [])
        from apps.employee.models import Employee
        for emp_id in employee_ids:
            try:
                emp = Employee.objects.get(id=emp_id)
                OrderMember.objects.create(
                    order=order,
                    employee=emp,
                    skill=order.skill,
                    unit_price=order.unit_price,
                    duration=order.duration,
                    amount=order.pay_amount / len(employee_ids) if employee_ids else 0,
                )
                emp.status = 'busy'
                emp.save(update_fields=['status'])
            except Exception:
                pass
        order.status = OrderStatus.IN_PROGRESS
        order.assigner = request.user
        order.assign_time = timezone.now()
        order.start_time = timezone.now()
        order.save()
        return success_response(msg='派单成功')

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        order = self.get_object()
        order.status = OrderStatus.IN_PROGRESS
        order.start_time = timezone.now()
        order.save()
        order.order_members.all().update(status='in_progress', start_time=timezone.now())
        return success_response(msg='开始服务')

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        order = self.get_object()
        if order.status != OrderStatus.IN_PROGRESS:
            return error_response(msg='订单状态不正确')
        order.status = OrderStatus.COMPLETED
        order.end_time = timezone.now()
        order.complete_time = timezone.now()
        order.save()
        order.order_members.all().update(status='completed', end_time=timezone.now())
        from apps.employee.models import Employee
        for member in order.order_members.all():
            member.employee.status = 'idle'
            member.employee.order_count += 1
            member.employee.total_duration += order.duration
            member.employee.save(update_fields=['status', 'order_count', 'total_duration'])
        return success_response(msg='订单已完成')

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        order = self.get_object()
        reason = request.data.get('reason', '')
        order.status = OrderStatus.CANCELLED
        order.cancel_time = timezone.now()
        order.cancel_reason = reason
        order.save()
        order.order_members.all().update(status='cancelled')
        from apps.employee.models import Employee
        for member in order.order_members.all():
            member.employee.status = 'idle'
            member.employee.save(update_fields=['status'])
        return success_response(msg='订单已取消')

    @action(detail=True, methods=['post'], url_path='refund')
    def refund(self, request, pk=None):
        order = self.get_object()
        refund_amount = request.data.get('refund_amount', order.pay_amount)
        reason = request.data.get('reason', '')
        refund = OrderRefund.objects.create(
            order=order,
            customer=order.customer,
            refund_amount=refund_amount,
            refund_reason=reason,
            applicant=request.user,
        )
        return success_response(OrderRefundSerializer(refund).data, msg='退款申请已提交')

    @action(detail=True, methods=['post'], url_path='comment')
    def comment(self, request, pk=None):
        order = self.get_object()
        if order.status != OrderStatus.COMPLETED:
            return error_response(msg='订单未完成，无法评价')
        rating = request.data.get('rating', 5)
        content = request.data.get('content', '')
        tags = request.data.get('tags', '')
        member_id = request.data.get('member_id')
        if member_id:
            member = order.order_members.filter(id=member_id, is_deleted=False).first()
            if not member:
                return error_response(msg='订单成员不存在')
        else:
            member = order.order_members.filter(is_deleted=False).first()
        employee = member.employee if member else None
        if not employee:
            return error_response(msg='评价的打手不存在')

        existing_qs = OrderComment.objects.filter(order=order, is_deleted=False)
        if member:
            existing_qs = existing_qs.filter(
                Q(member=member) | Q(member__isnull=True, employee=employee)
            )
        else:
            existing_qs = existing_qs.filter(employee=employee)
        comment = existing_qs.first()
        if comment:
            comment.rating = rating
            comment.content = content
            comment.tags = tags
            comment.save(update_fields=['rating', 'content', 'tags', 'updated_at'])
        else:
            comment = create_order_comment_with_retry(
                order=order,
                member=member,
                customer=order.customer,
                employee=employee,
                rating=rating,
                content=content,
                tags=tags,
            )

        total_members = order.order_members.filter(
            is_deleted=False, employee__isnull=False
        ).values('employee').distinct().count()
        reviewed_count = OrderComment.objects.filter(
            order=order, is_deleted=False
        ).values('employee').distinct().count()
        if reviewed_count >= total_members:
            order.status = OrderStatus.REVIEWED
            order.save(update_fields=['status', 'updated_at'])
        if employee:
            total_comments = employee.comments.filter(is_deleted=False).count()
            if total_comments > 0:
                from django.db.models import Avg
                avg_rating = employee.comments.filter(is_deleted=False).aggregate(avg=Avg('rating'))['avg'] or 5.0
                employee.rating = round(avg_rating, 2)
                employee.save(update_fields=['rating'])
        return success_response(OrderCommentSerializer(comment).data, msg='评价成功')

    @action(detail=False, methods=['get'], url_path='status-count')
    def status_count(self, request):
        from django.db.models import Count
        counts = Order.objects.filter(is_deleted=False).values('status').annotate(count=Count('id'))
        data = {item['status']: item['count'] for item in counts}
        return success_response(data)

    @action(detail=True, methods=['post'], url_path='add-member')
    def add_member(self, request, pk=None):
        order = self.get_object()
        employee_id = request.data.get('employee')
        from apps.employee.models import Employee
        try:
            emp = Employee.objects.get(id=employee_id)
            member = OrderMember.objects.create(
                order=order,
                employee=emp,
                skill=order.skill,
                unit_price=order.unit_price,
                duration=order.duration,
                amount=order.unit_price * order.duration / 60 if order.duration else 0,
            )
            emp.status = 'busy'
            emp.save(update_fields=['status'])
            return success_response(OrderMemberSerializer(member).data, msg='添加成功')
        except Employee.DoesNotExist:
            return error_response(msg='陪玩师不存在')

    @action(detail=True, methods=['post'], url_path='remove-member')
    def remove_member(self, request, pk=None):
        order = self.get_object()
        member_id = request.data.get('member_id')
        try:
            member = OrderMember.objects.get(id=member_id, order=order)
            member.employee.status = 'idle'
            member.employee.save(update_fields=['status'])
            member.delete()
            return success_response(msg='移除成功')
        except OrderMember.DoesNotExist:
            return error_response(msg='订单成员不存在')


class OrderMemberViewSet(BaseModelViewSet):
    queryset = OrderMember.objects.all()
    serializer_class = OrderMemberSerializer
    filterset_fields = ['status', 'order', 'employee']
    search_fields = ['order__order_no', 'employee__nickname']

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        member = self.get_object()
        member.status = 'accepted'
        member.accept_time = timezone.now()
        member.save()
        return success_response(msg='已接单')

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        member = self.get_object()
        member.status = 'in_progress'
        member.start_time = timezone.now()
        member.save()
        return success_response(msg='开始服务')

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        member = self.get_object()
        member.status = 'completed'
        member.end_time = timezone.now()
        member.save()
        member.employee.status = 'idle'
        member.employee.save(update_fields=['status'])
        return success_response(msg='服务完成')


class OrderPriceViewSet(BaseModelViewSet):
    queryset = OrderPrice.objects.all()
    serializer_class = OrderPriceSerializer
    filterset_fields = ['status', 'skill', 'level']
    search_fields = ['skill__name']


class OrderCommentViewSet(BaseModelViewSet):
    queryset = OrderComment.objects.all()
    serializer_class = OrderCommentSerializer
    filterset_fields = ['rating', 'is_anonymous', 'employee', 'customer']
    search_fields = ['order__order_no', 'content']
    ordering_fields = ['rating', 'created_at']

    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, pk=None):
        comment = self.get_object()
        reply = request.data.get('reply', '')
        comment.reply = reply
        comment.reply_time = timezone.now()
        comment.save()
        return success_response(msg='回复成功')


class OrderRefundViewSet(BaseModelViewSet):
    queryset = OrderRefund.objects.all()
    serializer_class = OrderRefundSerializer
    filterset_fields = ['status', 'refund_method', 'order', 'customer']
    search_fields = ['refund_no', 'order__order_no']

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        refund = self.get_object()
        if refund.status != 'pending':
            return error_response(msg='退款申请状态不正确')
        refund.status = 'approved'
        refund.auditor = request.user
        refund.audit_time = timezone.now()
        refund.audit_remark = request.data.get('remark', '')
        refund.save()
        order = refund.order
        order.status = OrderStatus.REFUNDED
        order.save()
        return success_response(msg='审核通过')

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        refund = self.get_object()
        if refund.status != 'pending':
            return error_response(msg='退款申请状态不正确')
        refund.status = 'rejected'
        refund.auditor = request.user
        refund.audit_time = timezone.now()
        refund.audit_remark = request.data.get('remark', '')
        refund.save()
        return success_response(msg='审核拒绝')

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_refund(self, request, pk=None):
        refund = self.get_object()
        if refund.status != 'approved':
            return error_response(msg='退款状态不正确')
        refund.status = 'completed'
        refund.complete_time = timezone.now()
        refund.save()
        return success_response(msg='退款完成')
