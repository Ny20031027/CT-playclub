import os

from django.core.asgi import get_asgi_application

# Match WSGI startup behavior: production containers provide DB_HOST.
if os.environ.get('DB_HOST'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

django_application = get_asgi_application()

from apps.notice.realtime import NoticeWebSocketApp

notice_websocket_application = NoticeWebSocketApp()


async def application(scope, receive, send):
    if scope.get('type') == 'websocket' and scope.get('path') == '/ws/notices/':
        await notice_websocket_application(scope, receive, send)
        return
    await django_application(scope, receive, send)
