from rest_framework import serializers
from apps.common.media import build_media_url
from .models import DailyStat, MonthlyStat, EmployeeRank


class DailyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyStat
        fields = '__all__'


class MonthlyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyStat
        fields = '__all__'


class EmployeeRankSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    employee_avatar = serializers.SerializerMethodField()

    def get_employee_avatar(self, obj):
        return build_media_url(obj.employee.avatar if obj.employee else '', self.context.get('request'))

    class Meta:
        model = EmployeeRank
        fields = ['id', 'date', 'period', 'employee', 'employee_name',
                  'employee_avatar', 'order_count', 'total_duration',
                  'total_amount', 'avg_rating', 'rank']
