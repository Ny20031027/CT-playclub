from rest_framework import serializers
from .models import (
    Schedule, Shift, Leave, Attendance, Booking
)


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'name', 'start_time', 'end_time', 'type', 'sort',
                  'status', 'remark', 'created_at']
        read_only_fields = ['id', 'created_at']


class ScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    type_text = serializers.CharField(source='get_type_display', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Schedule
        fields = ['id', 'employee', 'employee_name', 'date', 'shift', 'shift_name',
                  'start_time', 'end_time', 'type', 'type_text', 'status',
                  'status_text', 'check_in_time', 'check_out_time', 'remark',
                  'creator', 'creator_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'check_in_time', 'check_out_time',
                            'created_at', 'updated_at']


class LeaveSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    approver_name = serializers.CharField(source='approver.username', read_only=True)
    leave_type_text = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Leave
        fields = ['id', 'employee', 'employee_name', 'leave_type', 'leave_type_text',
                  'start_time', 'end_time', 'duration', 'reason', 'status',
                  'status_text', 'approver', 'approver_name', 'approve_time',
                  'approve_remark', 'created_at', 'updated_at']
        read_only_fields = ['id', 'approve_time', 'created_at', 'updated_at']


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'employee_name', 'date', 'check_in_time',
                  'check_out_time', 'work_duration', 'status', 'status_text',
                  'late_minutes', 'early_minutes', 'remark', 'check_in_ip',
                  'check_out_ip', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class BookingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    customer_name = serializers.CharField(source='customer.nickname', read_only=True)
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'employee', 'employee_name', 'customer', 'customer_name',
                  'date', 'start_time', 'end_time', 'duration', 'status',
                  'status_text', 'skill', 'skill_name', 'remark',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
