from rest_framework import serializers
from .models import UploadFile


class UploadFileSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)

    class Meta:
        model = UploadFile
        fields = ['id', 'file', 'file_name', 'file_size', 'file_type',
                  'mime_type', 'md5', 'uploader', 'uploader_name', 'category',
                  'storage_type', 'url', 'width', 'height', 'duration',
                  'created_at']
        read_only_fields = ['id', 'file_name', 'file_size', 'file_type',
                            'mime_type', 'md5', 'uploader', 'storage_type',
                            'url', 'width', 'height', 'duration', 'created_at']
