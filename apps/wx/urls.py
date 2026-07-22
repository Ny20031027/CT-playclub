from django.urls import path
from . import views
from .role_views import wx_login, test_login, user_profile

urlpatterns = [
    # 登录
    path('login/', wx_login, name='wx-login'),
    path('test-login/', test_login, name='wx-test-login'),
    path('update-user/', views.wx_update_user, name='wx-update-user'),
    path('bind-phone/', views.wx_bind_phone, name='wx-bind-phone'),

    # 首页
    path('home/', views.home_data, name='wx-home'),

    # 游戏分类
    path('games/', views.game_list, name='wx-game-list'),

    # 陪玩师
    path('employees/', views.employee_list, name='wx-employee-list'),
    path('employees/<int:emp_id>/', views.employee_detail, name='wx-employee-detail'),

    # 订单
    path('orders/create/', views.create_order, name='wx-create-order'),
    path('orders/create-self-service/', views.create_self_service_order, name='wx-create-self-service-order'),
    path('orders/dispatch-hall/', views.dispatch_hall, name='wx-dispatch-hall'),
    path('orders/', views.my_orders, name='wx-my-orders'),
    path('orders/employee/', views.employee_orders, name='wx-employee-orders'),
    path('orders/<int:order_id>/', views.order_detail, name='wx-order-detail'),
    path('orders/<int:order_id>/pay/', views.pay_order, name='wx-pay-order'),
    path('orders/<int:order_id>/cancel/', views.cancel_order, name='wx-cancel-order'),
    path('orders/<int:order_id>/claim/', views.claim_order, name='wx-claim-order'),
    path('orders/<int:order_id>/invite/', views.invite_order_member, name='wx-invite-order-member'),
    path('orders/<int:order_id>/give-up/', views.give_up_order, name='wx-give-up-order'),
    path('orders/<int:order_id>/confirm/', views.confirm_order, name='wx-confirm-order'),
    path('orders/<int:order_id>/start/', views.start_order, name='wx-start-order'),
    path('orders/<int:order_id>/end/', views.end_order, name='wx-end-order'),
    path('orders/<int:order_id>/complete/', views.complete_order, name='wx-complete-order'),
    path('orders/<int:order_id>/comment/', views.comment_order, name='wx-comment-order'),
    path('orders/<int:order_id>/transfer/', views.transfer_order, name='wx-transfer-order'),
    path('orders/<int:order_id>/discount/', views.discount_order, name='wx-discount-order'),
    path('orders/<int:order_id>/kick/', views.kick_member, name='wx-kick-member'),
    path('orders/<int:order_id>/ticket/', views.create_support_ticket, name='wx-create-ticket'),
    path('tickets/', views.my_tickets, name='wx-my-tickets'),
    path('cs/tickets/', views.cs_ticket_list, name='wx-cs-ticket-list'),
    path('cs/tickets/<int:ticket_id>/close/', views.cs_close_ticket, name='wx-cs-close-ticket'),

    # 消息
    path('notices/', views.my_notices, name='wx-my-notices'),
    path('notices/unread-count/', views.unread_count, name='wx-unread-count'),
    path('notices/<int:notice_id>/read/', views.mark_read, name='wx-mark-read'),
    path('notices/read-all/', views.mark_all_read, name='wx-mark-all-read'),

    # 礼物
    path('gifts/', views.gift_list, name='wx-gift-list'),

    # 客服配置
    path('customer-service/', views.customer_service, name='wx-customer-service'),
    path('cs/send/', views.send_cs_message, name='wx-cs-send'),
    path('cs/messages/', views.get_cs_messages, name='wx-cs-messages'),
    path('cs/unread/', views.get_cs_unread_count, name='wx-cs-unread'),
    path('cs/chat-list/', views.get_cs_chat_list, name='wx-cs-chat-list'),
    path('cs/chat-messages/', views.get_cs_chat_messages, name='wx-cs-chat-messages'),
    path('cs/reply/', views.send_cs_reply, name='wx-cs-reply'),

    # 个人中心
    path('profile/', user_profile, name='wx-profile'),
    path('profile/update/', views.update_profile, name='wx-update-profile'),
    path('skills/my/', views.get_my_skills, name='wx-get-my-skills'),
    path('skills/all/', views.get_all_skills, name='wx-get-all-skills'),
    path('skills/update/', views.update_my_skills, name='wx-update-my-skills'),
    path('tags/all/', views.get_all_tags, name='wx-get-all-tags'),

    # 组队
    path('team/my/', views.get_my_team, name='wx-get-my-team'),
    path('team/create/', views.create_team, name='wx-create-team'),
    path('team/invite/', views.invite_to_team, name='wx-invite-team'),
    path('team/handle-invite/', views.handle_team_invite, name='wx-handle-team-invite'),
    path('team/leave/', views.leave_team, name='wx-leave-team'),
]
