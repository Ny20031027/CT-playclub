from django.db import models
from apps.common.models import BaseModel
from apps.account.models import User


class UploadFile(BaseModel):
    file = models.FileField(upload_to='uploads/%Y/%m/%d/', verbose_name='文件')
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME类型')
    md5 = models.CharField(max_length=32, blank=True, verbose_name='MD5值')
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='uploaded_files', verbose_name='上传人')
    category = models.CharField(max_length=50, default='other', choices=[
        ('avatar', '头像'),
        ('image', '图片'),
        ('video', '视频'),
        ('audio', '音频'),
        ('document', '文档'),
        ('contract', '合同'),
        ('other', '其他'),
    ], verbose_name='分类')
    storage_type = models.CharField(max_length=20, default='local', choices=[
        ('local', '本地存储'),
        ('oss', '阿里云OSS'),
        ('cos', '腾讯云COS'),
        ('minio', 'MinIO'),
    ], verbose_name='存储方式')
    url = models.CharField(max_length=500, blank=True, verbose_name='访问URL')
    width = models.IntegerField(null=True, blank=True, verbose_name='宽度(像素)')
    height = models.IntegerField(null=True, blank=True, verbose_name='高度(像素)')
    duration = models.IntegerField(null=True, blank=True, verbose_name='时长(秒)')

    class Meta:
        db_table = 'upload_file'
        verbose_name = '上传文件'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.file_name
