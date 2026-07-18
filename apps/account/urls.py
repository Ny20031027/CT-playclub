from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuthViewSet, UserViewSet, RoleViewSet, PermissionViewSet,
    DepartmentViewSet, LoginLogViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'login-logs', LoginLogViewSet, basename='login-log')

auth_router = DefaultRouter()
auth_router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(auth_router.urls)),
]
