from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet, OrderMemberViewSet, OrderPriceViewSet,
    OrderCommentViewSet, OrderRefundViewSet
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'members', OrderMemberViewSet, basename='order-member')
router.register(r'prices', OrderPriceViewSet, basename='order-price')
router.register(r'comments', OrderCommentViewSet, basename='order-comment')
router.register(r'refunds', OrderRefundViewSet, basename='order-refund')

urlpatterns = [
    path('', include(router.urls)),
]
