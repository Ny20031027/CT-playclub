import os
import threading
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = '公共模块'

    def ready(self):
        # 仅在生产环境且 DB_HOST 不是默认值时自动迁移
        if os.environ.get('DB_HOST') and os.environ.get('DB_HOST') != '127.0.0.1':
            # 在后台线程执行 migrate，避免阻塞启动
            threading.Thread(target=self._auto_migrate, daemon=True).start()

    def _auto_migrate(self):
        import time
        from django.core.management import call_command
        # 等待数据库就绪
        for i in range(30):
            try:
                from django.db import connections
                connections['default'].ensure_connection()
                break
            except Exception:
                time.sleep(2)
        try:
            call_command('migrate', '--run-syncdb', verbosity=0)
        except Exception as e:
            import logging
            logging.getLogger('django').warning(f'Auto migrate failed: {e}')
