from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UploadViewSet

router = DefaultRouter()
router.register(r'files', UploadViewSet, basename='upload-file')

urlpatterns = [
    path('', include(router.urls)),
]
