"""
清理旧逻辑遗留的 OrderMember 记录。
旧逻辑：打手接取直接创建 OrderMember。
新逻辑：打手接取只创建 OrderCandidate，客户选人后才创建 OrderMember。
published 状态的订单不应有 OrderMember（除非是预约订单的预分配）。
"""
from django.db import migrations


def cleanup_old_order_members(apps, schema_editor):
    Order = apps.get_model('order', 'Order')
    OrderMember = apps.get_model('order', 'OrderMember')

    published_orders = Order.objects.filter(status='published', is_deleted=False)
    for order in published_orders:
        # 预约订单（assigned_employee 不为空）可能有预分配的成员，保留
        if order.assigned_employee_id:
            continue
        # 删除 published 状态订单上的旧 OrderMember 记录
        OrderMember.objects.filter(order=order, is_deleted=False).update(is_deleted=True)


def reverse_cleanup(apps, schema_editor):
    pass  # 不可逆操作，不做回滚


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0014_add_order_candidate'),
    ]

    operations = [
        migrations.RunPython(cleanup_old_order_members, reverse_cleanup),
    ]
