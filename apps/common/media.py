from django.conf import settings


def build_media_url(value, request=None):
    if not value:
        return ''

    value_str = str(value).strip()
    if not value_str:
        return ''
    if value_str.startswith(('http://', 'https://')):
        return value_str
    if value_str.startswith('//'):
        return f'https:{value_str}'

    if value_str.startswith('/'):
        return request.build_absolute_uri(value_str) if request else value_str

    if value_str.startswith('media/'):
        path = f'/{value_str}'
        return request.build_absolute_uri(path) if request else path

    cos_domain = getattr(settings, 'COS_DOMAIN', '').strip().rstrip('/')
    if cos_domain:
        if not cos_domain.startswith(('http://', 'https://')):
            cos_domain = f'https://{cos_domain}'
        return f'{cos_domain}/{value_str.lstrip("/")}'

    cos_bucket = getattr(settings, 'COS_BUCKET', '').strip()
    cos_region = getattr(settings, 'COS_REGION', 'ap-guangzhou').strip()
    if cos_bucket:
        return f'https://{cos_bucket}.cos.{cos_region}.myqcloud.com/{value_str.lstrip("/")}'

    path = f'{settings.MEDIA_URL.rstrip("/")}/{value_str.lstrip("/")}'
    return request.build_absolute_uri(path) if request else path
