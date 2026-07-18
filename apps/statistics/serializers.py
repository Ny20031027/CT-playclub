from rest_framework import serializers
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
        if obj.employee and obj.employee.avatar:
            return obj.employee.avatar.url
        return ''

    class Meta:
        model = EmployeeRank
        fields = ['id', 'date', 'period', 'employee', 'employee_name',
                  'employee_avatar', 'order_count', 'total_duration',
                  'total_amount', 'avg_rating', 'rank']
