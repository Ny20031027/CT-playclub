from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConfigViewSet, DictionaryViewSet, DictionaryItemViewSet,
    OperationLogViewSet, ErrorLogViewSet, BannerManageViewSet,
    AnnouncementManageViewSet
)
from apps.wx.views import GameCategoryViewSet

router = DefaultRouter()
router.register(r'configs', ConfigViewSet, basename='sys-config')
router.register(r'dictionaries', DictionaryViewSet, basename='sys-dictionary')
router.register(r'dictionary-items', DictionaryItemViewSet, basename='sys-dictionary-item')
router.register(r'operation-logs', OperationLogViewSet, basename='sys-operation-log')
router.register(r'error-logs', ErrorLogViewSet, basename='sys-error-log')
router.register(r'game-categories', GameCategoryViewSet, basename='sys-game-category')
router.register(r'banners', BannerManageViewSet, basename='sys-banner')
router.register(r'announcements', AnnouncementManageViewSet, basename='sys-announcement')

urlpatterns = [
    path('', include(router.urls)),
]
