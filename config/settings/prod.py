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

# 生产环境只输出到控制台，云托管从 stdout 采集日志
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
