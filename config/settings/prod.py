from .base import *

DEBUG = False

ALLOWED_HOSTS = ['*']

# 生产环境使用微信云托管 MySQL，通过环境变量配置
# DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'playclub-cache',
    }
}
