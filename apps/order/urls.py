from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet, OrderMemberViewSet, OrderPriceViewSet,
    OrderCommentViewSet, OrderRefundViewSet, SupportTicketViewSet
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'members', OrderMemberViewSet, basename='order-member')
router.register(r'prices', OrderPriceViewSet, basename='order-price')
router.register(r'comments', OrderCommentViewSet, basename='order-comment')
router.register(r'refunds', OrderRefundViewSet, basename='order-refund')
router.register(r'tickets', SupportTicketViewSet, basename='support-ticket')

urlpatterns = [
    path('', include(router.urls)),
]
