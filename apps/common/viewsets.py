from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.response import Response
from .models import BaseModel
from .response import success_response


class BaseModelViewSet(ModelViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset.model, 'is_deleted'):
            queryset = queryset.filter(is_deleted=False)
        return queryset

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return success_response(response.data, msg='创建成功')

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return success_response(response.data, msg='更新成功')

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return success_response(msg='删除成功')

    def perform_destroy(self, instance):
        if hasattr(instance, 'is_deleted'):
            instance.is_deleted = True
            instance.save(update_fields=['is_deleted', 'updated_at'])
        else:
            instance.delete()
