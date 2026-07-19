from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import os
import hashlib
import time
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import UploadFile
from .serializers import UploadFileSerializer


def upload_to_cos(file_obj, file_path):
    """上传文件到腾讯云 COS"""
    from qcloud_cos import CosConfig, CosS3Client
    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
    )
    client = CosS3Client(config)
    client.upload_file(
        Bucket=settings.COS_BUCKET,
        Key=file_path,
        Body=file_obj,
        EnableMD5=False,
    )
    # 构建访问 URL
    if settings.COS_DOMAIN:
        return f'https://{settings.COS_DOMAIN}/{file_path}'
    else:
        return f'https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{file_path}'


class UploadViewSet(BaseModelViewSet):
    queryset = UploadFile.objects.all()
    serializer_class = UploadFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['category', 'file_type', 'storage_type', 'uploader']
    search_fields = ['file_name']
    ordering_fields = ['file_size', 'created_at']

    @action(detail=False, methods=['post'], url_path='image')
    def upload_image(self, request):
        return self._handle_upload(request, 'image', ['image/jpeg', 'image/png', 'image/gif', 'image/webp'])

    @action(detail=False, methods=['post'], url_path='file')
    def upload_file(self, request):
        return self._handle_upload(request, 'other')

    @action(detail=False, methods=['post'], url_path='avatar')
    def upload_avatar(self, request):
        return self._handle_upload(request, 'avatar', ['image/jpeg', 'image/png', 'image/gif', 'image/webp'])

    def _handle_upload(self, request, category, allowed_mime_types=None):
        if 'file' not in request.FILES:
            return error_response(msg='请选择文件')
        file_obj = request.FILES['file']
        if file_obj.size > 100 * 1024 * 1024:
            return error_response(msg='文件大小不能超过100MB')
        if allowed_mime_types and file_obj.content_type not in allowed_mime_types:
            return error_response(msg=f'不支持的文件类型: {file_obj.content_type}')
        
        file_name = file_obj.name
        file_size = file_obj.size
        file_ext = os.path.splitext(file_name)[1].lower()
        file_type = self._get_file_type(file_ext)
        md5 = self._calculate_md5(file_obj)
        
        # 生成存储路径
        from datetime import date
        today = date.today().strftime('%Y/%m/%d')
        file_path = f'uploads/{today}/{md5}{file_ext}'
        
        # 判断使用 COS 还是本地存储
        use_cos = bool(settings.COS_SECRET_ID and settings.COS_SECRET_KEY and settings.COS_BUCKET)
        
        if use_cos:
            # 上传到 COS
            try:
                file_obj.seek(0)
                full_url = upload_to_cos(file_obj, file_path)
                storage_type = 'cos'
                local_url = ''
            except Exception as e:
                import logging
                logging.getLogger('django').error(f'COS upload failed: {e}')
                return error_response(msg='文件上传失败')
        else:
            # 本地存储
            upload = UploadFile.objects.create(
                file=file_obj,
                file_name=file_name,
                file_size=file_size,
                file_type=file_type,
                mime_type=file_obj.content_type or '',
                md5=md5,
                uploader=request.user if request.user.is_authenticated else None,
                category=category,
                storage_type='local',
                url='',
            )
            local_url = upload.file.url
            scheme = request.scheme
            host = request.get_host()
            full_url = f'{scheme}://{host}{local_url}'
            storage_type = 'local'
        
        # 保存记录
        upload = UploadFile.objects.create(
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            mime_type=file_obj.content_type or '',
            md5=md5,
            uploader=request.user if request.user.is_authenticated else None,
            category=category,
            storage_type=storage_type,
            url=full_url,
        )
        
        data = {
            'id': upload.id,
            'url': full_url,
            'file_name': upload.file_name,
            'file_size': upload.file_size,
            'file_type': upload.file_type,
            'md5': upload.md5,
            'created_at': upload.created_at,
        }
        return success_response(data, msg='上传成功')

    def _get_file_type(self, ext):
        image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
        video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv']
        audio_exts = ['.mp3', '.wav', '.flac', '.aac', '.ogg']
        doc_exts = ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.md']
        if ext in image_exts:
            return 'image'
        elif ext in video_exts:
            return 'video'
        elif ext in audio_exts:
            return 'audio'
        elif ext in doc_exts:
            return 'document'
        else:
            return 'other'

    def _calculate_md5(self, file_obj):
        md5 = hashlib.md5()
        for chunk in file_obj.chunks():
            md5.update(chunk)
        file_obj.seek(0)
        return md5.hexdigest()
