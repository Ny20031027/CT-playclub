from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.utils import timezone
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import (
    Schedule, Shift, Leave, Attendance, Booking, CSSchedule
)
from .serializers import (
    ScheduleSerializer, ShiftSerializer, LeaveSerializer,
    AttendanceSerializer, BookingSerializer
)


class ShiftViewSet(BaseModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    filterset_fields = ['status', 'type']
    search_fields = ['name']
    ordering_fields = ['sort', 'start_time']


class ScheduleViewSet(BaseModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    filterset_fields = ['type', 'status', 'employee', 'shift']
    search_fields = ['employee__nickname', 'remark']
    ordering_fields = ['date', 'created_at']

    @action(detail=False, methods=['get'], url_path='week')
    def week_schedule(self, request):
        from datetime import timedelta
        date = request.query_params.get('date', timezone.now().date())
        if isinstance(date, str):
            from datetime import datetime
            date = datetime.strptime(date, '%Y-%m-%d').date()
        start_of_week = date - timedelta(days=date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        schedules = self.get_queryset().filter(
            date__gte=start_of_week,
            date__lte=end_of_week
        )
        serializer = self.get_serializer(schedules, many=True)
        return success_response(serializer.data)

    @action(detail=False, methods=['get'], url_path='month')
    def month_schedule(self, request):
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{last_day}"
        schedules = self.get_queryset().filter(date__gte=start_date, date__lte=end_date)
        serializer = self.get_serializer(schedules, many=True)
        return success_response(serializer.data)

    @action(detail=True, methods=['post'], url_path='check-in')
    def check_in(self, request, pk=None):
        schedule = self.get_object()
        if schedule.status != 'scheduled':
            return error_response(msg='当前状态不能签到')
        schedule.status = 'checked_in'
        schedule.check_in_time = timezone.now()
        schedule.save()
        return success_response(msg='签到成功')

    @action(detail=True, methods=['post'], url_path='check-out')
    def check_out(self, request, pk=None):
        schedule = self.get_object()
        if schedule.status != 'checked_in':
            return error_response(msg='当前状态不能签退')
        schedule.status = 'checked_out'
        schedule.check_out_time = timezone.now()
        schedule.save()
        return success_response(msg='签退成功')

    @action(detail=False, methods=['post'], url_path='batch-create')
    def batch_create(self, request):
        employee_ids = request.data.get('employee_ids', [])
        date_list = request.data.get('dates', [])
        shift_id = request.data.get('shift')
        schedule_type = request.data.get('type', 'work')
        from apps.employee.models import Employee
        created_count = 0
        for emp_id in employee_ids:
            try:
                emp = Employee.objects.get(id=emp_id)
                for date_str in date_list:
                    from datetime import datetime
                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    schedule, created = Schedule.objects.get_or_create(
                        employee=emp,
                        date=date,
                        defaults={
                            'shift_id': shift_id,
                            'type': schedule_type,
                            'creator': request.user,
                        }
                    )
                    if created:
                        created_count += 1
            except Exception:
                pass
        return success_response({'created': created_count}, msg='批量排班成功')


class LeaveViewSet(BaseModelViewSet):
    queryset = Leave.objects.all()
    serializer_class = LeaveSerializer
    filterset_fields = ['leave_type', 'status', 'employee']
    search_fields = ['employee__nickname', 'reason']
    ordering_fields = ['start_time', 'created_at']

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        leave = self.get_object()
        if leave.status != 'pending':
            return error_response(msg='请假状态不正确')
        leave.status = 'approved'
        leave.approver = request.user
        leave.approve_time = timezone.now()
        leave.approve_remark = request.data.get('remark', '')
        leave.save()
        return success_response(msg='审核通过')

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        leave = self.get_object()
        if leave.status != 'pending':
            return error_response(msg='请假状态不正确')
        leave.status = 'rejected'
        leave.approver = request.user
        leave.approve_time = timezone.now()
        leave.approve_remark = request.data.get('remark', '')
        leave.save()
        return success_response(msg='审核拒绝')

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        leave = self.get_object()
        if leave.status not in ['pending', 'approved']:
            return error_response(msg='当前状态不能取消')
        leave.status = 'cancelled'
        leave.save()
        return success_response(msg='已取消')


class AttendanceViewSet(BaseModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    filterset_fields = ['status', 'employee']
    search_fields = ['employee__nickname']
    ordering_fields = ['date', 'work_duration']

    @action(detail=False, methods=['get'], url_path='month-stat')
    def month_stat(self, request):
        employee_id = request.query_params.get('employee')
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-{last_day}"
        queryset = self.get_queryset().filter(date__gte=start_date, date__lte=end_date)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        from django.db.models import Count, Sum
        stats = queryset.values('status').annotate(
            count=Count('id'),
            total_hours=Sum('work_duration')
        )
        data = {item['status']: item for item in stats}
        return success_response(data)


class BookingViewSet(BaseModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    filterset_fields = ['status', 'employee', 'customer', 'skill']
    search_fields = ['employee__nickname', 'customer__nickname']
    ordering_fields = ['date', 'created_at']

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'pending':
            return error_response(msg='预约状态不正确')
        booking.status = 'confirmed'
        booking.save()
        return success_response(msg='预约已确认')

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status in ['completed', 'cancelled']:
            return error_response(msg='预约状态不正确')
        booking.status = 'cancelled'
        booking.save()
        return success_response(msg='预约已取消')

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'confirmed':
            return error_response(msg='预约状态不正确')
        booking.status = 'completed'
        booking.save()
        return success_response(msg='预约已完成')


from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date, parse_time


@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cs_schedule_list(request):
    """客服排班列表"""
    from apps.employee.models import Employee

    if request.method == 'GET':
        schedules = CSSchedule.objects.select_related('employee')
        data = []
        for s in schedules:
            day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            data.append({
                'id': s.id,
                'employee_id': s.employee_id,
                'employee_name': s.employee.nickname or s.employee.real_name,
                'day_of_week': s.day_of_week,
                'day_name': day_names[s.day_of_week],
                'start_time': str(s.start_time),
                'end_time': str(s.end_time),
                'status': s.status,
            })
        return success_response(data)

    elif request.method == 'POST':
        employee_id = request.data.get('employee_id')
        day_of_week = request.data.get('day_of_week')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')

        if not employee_id or day_of_week is None or not start_time or not end_time:
            return error_response(msg='请填写完整信息')

        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return error_response(msg='员工不存在')

        start = parse_time(start_time)
        end = parse_time(end_time)

        if not start or not end:
            return error_response(msg='时间格式错误')

        # 检查是否已存在该员工该星期的排班
        existing = CSSchedule.objects.filter(employee=employee, day_of_week=day_of_week).first()
        if existing:
            existing.start_time = start
            existing.end_time = end
            existing.save()
            return success_response(msg='更新成功', data={'id': existing.id})
        else:
            schedule = CSSchedule.objects.create(
                employee=employee,
                day_of_week=day_of_week,
                start_time=start,
                end_time=end,
                status=True,
            )
            return success_response(msg='添加成功', data={'id': schedule.id})


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([AllowAny])
def cs_schedule_delete(request, schedule_id):
    """删除客服排班"""
    try:
        schedule = CSSchedule.objects.get(id=schedule_id)
        schedule.delete()
        return success_response(msg='删除成功')
    except CSSchedule.DoesNotExist:
        return error_response(msg='排班不存在')
