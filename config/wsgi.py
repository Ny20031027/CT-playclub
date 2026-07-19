import os

from django.core.wsgi import get_wsgi_application

# 根据环境变量选择配置：有 DB_HOST 时用 prod，否则用 dev
if os.environ.get('DB_HOST'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_wsgi_application()
