from rest_framework import serializers
from .models import (
    Notice, UserNotice, EmployeeNotice, SmsLog, EmailLog
)


class NoticeSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    type_text = serializers.CharField(source='get_type_display', read_only=True)
    level_text = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Notice
        fields = ['id', 'title', 'content', 'type', 'type_text', 'level',
                  'level_text', 'sender', 'sender_name', 'target_type',
                  'target_ids', 'is_read', 'is_published', 'publish_time',
                  'jump_url', 'extra', 'remark', 'created_at', 'updated_at']
        read_only_fields = ['id', 'publish_time', 'created_at', 'updated_at']


class UserNoticeSerializer(serializers.ModelSerializer):
    notice_title = serializers.CharField(source='notice.title', read_only=True)
    notice_content = serializers.CharField(source='notice.content', read_only=True)
    notice_type = serializers.CharField(source='notice.type', read_only=True)
    notice_level = serializers.CharField(source='notice.level', read_only=True)
    notice_jump_url = serializers.CharField(source='notice.jump_url', read_only=True)

    class Meta:
        model = UserNotice
        fields = ['id', 'notice', 'notice_title', 'notice_content',
                  'notice_type', 'notice_level', 'notice_jump_url',
                  'is_read', 'read_time', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmployeeNoticeSerializer(serializers.ModelSerializer):
    notice_title = serializers.CharField(source='notice.title', read_only=True)
    notice_content = serializers.CharField(source='notice.content', read_only=True)
    notice_type = serializers.CharField(source='notice.type', read_only=True)
    notice_level = serializers.CharField(source='notice.level', read_only=True)
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = EmployeeNotice
        fields = ['id', 'notice', 'notice_title', 'notice_content',
                  'notice_type', 'notice_level', 'employee', 'employee_name',
                  'is_read', 'read_time', 'created_at']
        read_only_fields = ['id', 'created_at']


class SmsLogSerializer(serializers.ModelSerializer):
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SmsLog
        fields = ['id', 'phone', 'content', 'type', 'status', 'status_text',
                  'error_msg', 'send_time', 'created_at']
        read_only_fields = ['id', 'send_time', 'created_at']


class EmailLogSerializer(serializers.ModelSerializer):
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EmailLog
        fields = ['id', 'email', 'subject', 'content', 'type', 'status',
                  'status_text', 'error_msg', 'send_time', 'created_at']
        read_only_fields = ['id', 'send_time', 'created_at']
