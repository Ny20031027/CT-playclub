from rest_framework import serializers
from .models import (
    Wallet, Transaction, Settlement, SettlementDetail, Salary, Withdraw
)


class WalletSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Wallet
        fields = ['id', 'user', 'user_name', 'balance', 'frozen_amount',
                  'total_income', 'total_expense', 'type', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    type_text = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'wallet', 'wallet_id', 'employee', 'employee_name',
                  'order_no', 'transaction_no', 'type', 'type_text', 'category',
                  'amount', 'balance_after', 'remark', 'operator', 'operator_name',
                  'source', 'created_at']
        read_only_fields = ['id', 'transaction_no', 'created_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['transaction_no'] = f"TRX{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class SettlementDetailSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)

    class Meta:
        model = SettlementDetail
        fields = ['id', 'settlement', 'employee', 'employee_name', 'order_count',
                  'total_duration', 'total_amount', 'commission_amount',
                  'commission_rate', 'status']
        read_only_fields = ['id']


class SettlementSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)
    details = SettlementDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Settlement
        fields = ['id', 'settlement_no', 'type', 'status', 'status_text',
                  'total_amount', 'total_commission', 'total_profit', 'order_count',
                  'start_date', 'end_date', 'complete_time', 'operator',
                  'operator_name', 'remark', 'details', 'created_at']
        read_only_fields = ['id', 'settlement_no', 'created_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['settlement_no'] = f"SET{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class SalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Salary
        fields = ['id', 'salary_no', 'employee', 'employee_name', 'month',
                  'base_salary', 'commission', 'bonus', 'deduction',
                  'total_amount', 'status', 'status_text', 'pay_time',
                  'pay_method', 'operator', 'operator_name', 'remark',
                  'created_at']
        read_only_fields = ['id', 'salary_no', 'created_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['salary_no'] = f"SAL{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)


class WithdrawSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.nickname', read_only=True)
    auditor_name = serializers.CharField(source='auditor.username', read_only=True)
    status_text = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Withdraw
        fields = ['id', 'withdraw_no', 'employee', 'employee_name', 'amount',
                  'fee', 'actual_amount', 'withdraw_method', 'account_name',
                  'account_no', 'status', 'status_text', 'apply_time',
                  'audit_time', 'auditor', 'auditor_name', 'audit_remark',
                  'complete_time', 'remark', 'created_at']
        read_only_fields = ['id', 'withdraw_no', 'apply_time', 'audit_time',
                            'complete_time', 'created_at']

    def create(self, validated_data):
        import datetime
        import uuid
        validated_data['withdraw_no'] = f"WIT{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"
        return super().create(validated_data)
