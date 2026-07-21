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
        import logging
        logger = logging.getLogger('django')
        from django.core.management import call_command
        # 等待数据库就绪
        for i in range(30):
            try:
                from django.db import connections
                connections['default'].ensure_connection()
                break
            except Exception:
                time.sleep(2)
        
        # 先尝试合并冲突迁移
        try:
            logger.info('Attempting to merge migrations...')
            call_command('makemigrations', '--merge', '--noinput', verbosity=0)
        except Exception as e:
            logger.warning(f'Merge migrations failed (may be no conflicts): {e}')
        
        # 执行迁移
        try:
            logger.info('Starting auto migrate...')
            call_command('migrate', verbosity=1)
            logger.info('Auto migrate completed successfully')
        except Exception as e:
            logger.error(f'Auto migrate failed: {e}')
            # 尝试单独迁移每个应用
            for app_name in ['account', 'order', 'employee', 'customer', 'notice', 'system', 'finance', 'schedule', 'statistics', 'upload', 'wx']:
                try:
                    call_command('migrate', app_name, verbosity=0)
                    logger.info(f'Migrated {app_name} successfully')
                except Exception as e2:
                    logger.error(f'Failed to migrate {app_name}: {e2}')
            return
        
        # 自动创建超级管理员（如果不存在）
        self._create_default_admin()

    def _create_default_admin(self):
        try:
            from apps.account.models import User
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser(
                    username='admin',
                    password='admin123456',
                    phone='13800000000',
                    is_staff=True,
                )
                import logging
                logging.getLogger('django').info('Default admin created: admin / admin123456')
        except Exception as e:
            import logging
            logging.getLogger('django').warning(f'Create admin failed: {e}')
