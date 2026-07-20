# -*- coding: utf-8 -*-
import re

file_path = r'D:\CT电竞\PlayClub\apps\wx\views.py'

with open(file_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# 替换 give_up_order 函数
old_func = '''@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def give_up_order(request, order_id):
    """打手放弃订单（释放锁定的席位，返回派单大厅）"""
    user = request.user
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态是否可放弃
    if order.status not in ['published', 'confirming', 'claimed']:
        return error_response(msg='当前订单状态不可放弃')

    # 查找该打手的订单成员记录
    member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()

    if not member:
        return error_response(msg='您没有接取过该订单')

    is_formal_order = order.status in ['confirming', 'claimed']
    if is_formal_order and order.leader_id != employee.id:
        return error_response(msg='订单正式接取后，仅队长可以进行状态操作')

    if is_formal_order and order.leader_id == employee.id:
        OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).delete()
        order.status = 'published'
        order.locked_slots = 0
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=[
            'status', 'locked_slots', 'leader', 'customer_confirmed',
            'dasher_confirmed', 'updated_at'
        ])
        return success_response(msg='队长已取消正式接取，订单已回到派单大厅', data={'locked_slots': 0})

    # 释放席位（根据该成员锁定的席位数）
    slots_released = parse_member_slots(member)

    # 更新已锁定席位数
    order.locked_slots = max(0, order.locked_slots - slots_released)

    # 删除订单成员记录
    member.delete()

    # 检查是否还有其他成员
    remaining_members = OrderMember.objects.filter(
        order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
    ).count()

    if remaining_members == 0:
        # 没有其他成员了，恢复订单状态为 published，清除队长
        order.status = 'published'
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=['status', 'locked_slots', 'leader', 'customer_confirmed', 'dasher_confirmed', 'updated_at'])
    else:
        # 还有其他成员，如果放弃的是队长，需要转移队长
        if order.leader_id == employee.id:
            next_member = OrderMember.objects.filter(
                order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
            ).order_by('id').first()
            if next_member:
                order.leader = next_member.employee
            else:
                order.leader = None
        order.save(update_fields=['locked_slots', 'leader', 'updated_at'])

    return success_response(msg='已放弃', data={'locked_slots': order.locked_slots})'''

new_func = '''@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def give_up_order(request, order_id):
    """打手放弃订单（释放锁定的席位，返回派单大厅）
    规则：在订单未开始服务前（in_progress之前），任何打手都可以自由放弃
    """
    user = request.user
    try:
        employee = user.employee
    except Exception:
        return error_response(msg='您不是打手')

    try:
        order = Order.objects.select_for_update().get(id=order_id, is_deleted=False)
    except Order.DoesNotExist:
        return error_response(msg='订单不存在')

    # 检查订单状态是否可放弃（in_progress之前都可以放弃）
    if order.status not in ['published', 'confirming', 'claimed']:
        return error_response(msg='订单已开始服务，无法放弃')

    # 查找该打手的订单成员记录
    member = OrderMember.objects.filter(
        order=order, employee=employee, is_deleted=False, status__in=['accepted', 'in_progress']
    ).first()

    if not member:
        return error_response(msg='您没有接取过该订单')

    is_leader = order.leader_id == employee.id
    is_formal_order = order.status in ['confirming', 'claimed']

    # 队长放弃正式接取的订单 → 删除所有成员，回退到 published
    if is_formal_order and is_leader:
        OrderMember.objects.filter(order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES).delete()
        order.status = 'published'
        order.locked_slots = 0
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=[
            'status', 'locked_slots', 'leader', 'customer_confirmed',
            'dasher_confirmed', 'updated_at'
        ])
        return success_response(msg='队长已取消正式接取，订单已回到派单大厅', data={'locked_slots': 0})

    # 非队长成员放弃（或非正式阶段的队长放弃）
    # 释放席位（根据该成员锁定的席位数）
    slots_released = parse_member_slots(member)

    # 更新已锁定席位数
    order.locked_slots = max(0, order.locked_slots - slots_released)

    # 删除订单成员记录
    member.delete()

    # 检查是否还有其他成员
    remaining_members = OrderMember.objects.filter(
        order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
    ).count()

    if remaining_members == 0:
        # 没有其他成员了，恢复订单状态为 published，清除队长
        order.status = 'published'
        order.leader = None
        order.customer_confirmed = False
        order.dasher_confirmed = False
        order.save(update_fields=['status', 'locked_slots', 'leader', 'customer_confirmed', 'dasher_confirmed', 'updated_at'])
    else:
        # 还有其他成员，如果放弃的是队长，需要转移队长
        if is_leader:
            next_member = OrderMember.objects.filter(
                order=order, is_deleted=False, status__in=ACTIVE_ORDER_MEMBER_STATUSES
            ).order_by('id').first()
            if next_member:
                order.leader = next_member.employee
            else:
                order.leader = None
        order.save(update_fields=['locked_slots', 'leader', 'updated_at'])

    return success_response(msg='已放弃', data={'locked_slots': order.locked_slots})'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed give_up_order')
else:
    print('give_up_order not found or already modified')
