from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
import os
import hashlib
import logging
from apps.common.response import success_response, error_response
from apps.common.viewsets import BaseModelViewSet
from .models import UploadFile
from .serializers import UploadFileSerializer

logger = logging.getLogger(__name__)


IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def upload_to_cos(file_obj, file_path):
    """上传文件到腾讯云 COS"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise RuntimeError('COS SDK is not installed. Please install cos-python-sdk-v5.') from exc
    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
    )
    client = CosS3Client(config)
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Key=file_path,
        Body=file_obj,
        ContentType=getattr(file_obj, 'content_type', '') or 'application/octet-stream',
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
        return self._handle_upload(request, 'image', IMAGE_MIME_TYPES)

    @action(detail=False, methods=['post'], url_path='file')
    def upload_file(self, request):
        return self._handle_upload(request, 'other')

    @action(detail=False, methods=['post'], url_path='avatar')
    def upload_avatar(self, request):
        return self._handle_upload(request, 'avatar', IMAGE_MIME_TYPES)

    def _handle_upload(self, request, category, allowed_mime_types=None):
        if 'file' not in request.FILES:
            return error_response(msg='请选择文件')
        file_obj = request.FILES['file']
        if file_obj.size > 100 * 1024 * 1024:
            return error_response(msg='文件大小不能超过100MB')
        
        file_name = file_obj.name
        file_size = file_obj.size
        file_ext = os.path.splitext(file_name)[1].lower()
        detected_ext, detected_mime = self._detect_image_type(file_obj)
        if allowed_mime_types and not self._is_allowed_image(file_obj.content_type, file_ext, detected_mime):
            return error_response(msg=f'Unsupported file type: {file_obj.content_type or "unknown"}')
        if allowed_mime_types and detected_ext and file_ext not in IMAGE_EXTS:
            file_ext = detected_ext
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
                logger.info(f'COS upload success: {file_path}')
            except Exception as e:
                logger.exception(
                    'COS upload failed: bucket=%s region=%s key=%s error=%s',
                    settings.COS_BUCKET,
                    settings.COS_REGION,
                    file_path,
                    e,
                )
                return error_response(msg='COS文件上传失败，请检查后端日志')
        else:
            # 本地存储（容器重启后会丢失，建议配置 COS）
            logger.warning('Using local storage - files will be lost on container restart. Configure COS for persistent storage.')
            # 保存到本地
            from django.core.files.storage import default_storage
            local_path = default_storage.save(file_path, file_obj)
            scheme = request.scheme
            host = request.get_host()
            full_url = f'{scheme}://{host}/media/{local_path}'
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

    def _detect_image_type(self, file_obj):
        pos = file_obj.tell()
        header = file_obj.read(512)
        file_obj.seek(pos)
        if header.startswith(b'\xff\xd8\xff'):
            return '.jpg', 'image/jpeg'
        if header.startswith(b'\x89PNG\r\n\x1a\n'):
            return '.png', 'image/png'
        if header.startswith((b'GIF87a', b'GIF89a')):
            return '.gif', 'image/gif'
        if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
            return '.webp', 'image/webp'
        return '', ''

    def _is_allowed_image(self, content_type, file_ext, detected_mime):
        if content_type in IMAGE_MIME_TYPES or detected_mime in IMAGE_MIME_TYPES:
            return True
        if content_type and content_type.startswith('image/') and file_ext in IMAGE_EXTS:
            return True
        return file_ext in IMAGE_EXTS
