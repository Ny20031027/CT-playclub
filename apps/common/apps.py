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
        from django.db import connections
        
        # 等待数据库就绪
        for i in range(30):
            try:
                connections['default'].ensure_connection()
                break
            except Exception:
                time.sleep(2)
        
        # 直接用 SQL 确保关键列存在
        try:
            cursor = connections['default'].cursor()
            # 检查 assigned_employee_id 列是否存在
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'ord_order' 
                AND COLUMN_NAME = 'assigned_employee_id'
            """)
            if cursor.fetchone()[0] == 0:
                logger.info('Adding assigned_employee_id column...')
                cursor.execute("ALTER TABLE ord_order ADD COLUMN assigned_employee_id int NULL")
                logger.info('Column added successfully')
        except Exception as e:
            logger.error(f'Failed to add column via SQL: {e}')
        
        # 然后执行标准迁移
        try:
            call_command('migrate', verbosity=1)
            logger.info('Auto migrate completed')
        except Exception as e:
            logger.error(f'Auto migrate failed: {e}')
        
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
