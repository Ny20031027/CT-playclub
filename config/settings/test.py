from .base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test.sqlite3',
    }
}

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
MIDDLEWARE = [
    middleware for middleware in MIDDLEWARE
    if middleware != 'whitenoise.middleware.WhiteNoiseMiddleware'
]

# Historical production migrations contain MySQL-only repair SQL. Unit tests use
# current models directly so the business rules can run on an isolated SQLite DB.
MIGRATION_MODULES = {
    'account': None,
    'employee': None,
    'customer': None,
    'order': None,
    'finance': None,
    'schedule': None,
    'statistics': None,
    'notice': None,
    'upload': None,
    'system': None,
    'wx': None,
}
