import os
import threading
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = '公共模块'

    def ready(self):
        if os.environ.get('DB_HOST') and os.environ.get('DB_HOST') != '127.0.0.1':
            threading.Thread(target=self._auto_migrate, daemon=True).start()

    def _auto_migrate(self):
        import time
        import logging
        logger = logging.getLogger('django')
        from django.core.management import call_command
        from django.db import connections

        for i in range(30):
            try:
                connections['default'].ensure_connection()
                break
            except Exception:
                time.sleep(2)

        self._fix_columns(logger, connections)

        try:
            call_command('migrate', verbosity=1)
            logger.info('Auto migrate completed')
        except Exception as e:
            logger.error(f'Auto migrate failed: {e}')

        self._create_default_admin()

    def _fix_columns(self, logger, connections):
        try:
            cursor = connections['default'].cursor()

            # 添加 assigned_employee_id 列
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order' AND COLUMN_NAME = 'assigned_employee_id'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE ord_order ADD COLUMN assigned_employee_id int NULL")
                logger.info('Added ord_order.assigned_employee_id column')

            # 添加 ordercomment.member_id 列
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order_comment' AND COLUMN_NAME = 'member_id'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE ord_order_comment ADD COLUMN member_id int NULL")
                logger.info('Added ord_order_comment.member_id column')

            # 移除 ordercomment.order_id 的唯一约束（OneToOne 改 ForeignKey）
            cursor.execute("""
                SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order_comment'
                AND COLUMN_NAME = 'order_id' AND NON_UNIQUE = 0 AND INDEX_NAME != 'PRIMARY'
            """)
            idx = cursor.fetchone()
            if idx:
                cursor.execute(f"ALTER TABLE ord_order_comment DROP INDEX {idx[0]}")
                logger.info('Removed unique index on ord_order_comment.order_id')

            # 确保 order 表的 assigned_employee_id 允许 NULL
            cursor.execute("SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order' AND COLUMN_NAME = 'assigned_employee_id'")
            result = cursor.fetchone()
            if result and result[0] == 'NO':
                cursor.execute("ALTER TABLE ord_order MODIFY COLUMN assigned_employee_id int NULL")
                logger.info('ord_order.assigned_employee_id set to NULL')

            # 确保 ordercomment 表的 employee_id 和 member_id 允许 NULL
            for col in ['employee_id', 'member_id']:
                cursor.execute(f"SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order_comment' AND COLUMN_NAME = '{col}'")
                result = cursor.fetchone()
                if result and result[0] == 'NO':
                    cursor.execute(f"ALTER TABLE ord_order_comment MODIFY COLUMN {col} int NULL")
                    logger.info(f'ord_order_comment.{col} set to NULL')

            # 确保所有 employee_id 列允许 NULL
            fk_tables = ['ord_ordermember', 'fin_transaction', 'fin_settlement_detail', 'fin_salary', 'fin_withdraw']
            for table in fk_tables:
                try:
                    cursor.execute(f"SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' AND COLUMN_NAME = 'employee_id'")
                    result = cursor.fetchone()
                    if result and result[0] == 'NO':
                        cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY IF EXISTS {table}_employee_id_fk")
                        cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN employee_id int NULL")
                        cursor.execute(f"ALTER TABLE {table} ADD FOREIGN KEY (employee_id) REFERENCES emp_employee(id) ON DELETE SET NULL")
                        logger.info(f'{table}.employee_id set to NULL')
                except Exception as e:
                    logger.warning(f'Failed to fix {table}: {e}')

        except Exception as e:
            logger.error(f'Failed to update columns via SQL: {e}')

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
