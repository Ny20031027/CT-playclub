from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, CustomerLevelViewSet, CustomerTagViewSet,
    BlacklistViewSet, CustomerConsumeRecordViewSet,
    cs_list, cs_add, cs_remove
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'levels', CustomerLevelViewSet, basename='customer-level')
router.register(r'tags', CustomerTagViewSet, basename='customer-tag')
router.register(r'blacklists', BlacklistViewSet, basename='blacklist')
router.register(r'consume-records', CustomerConsumeRecordViewSet, basename='consume-record')

urlpatterns = [
    path('', include(router.urls)),
    path('cs-list/', cs_list, name='cs-list'),
    path('cs-add/', cs_add, name='cs-add'),
    path('cs-remove/<int:cs_id>/', cs_remove, name='cs-remove'),
]
