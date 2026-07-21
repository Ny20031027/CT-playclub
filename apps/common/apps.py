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
        
        # 直接用 SQL 确保关键列存在且允许 NULL
        try:
            cursor = connections['default'].cursor()

            # 确保 ord_order.assigned_employee_id 存在且允许 NULL
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_order' AND COLUMN_NAME = 'assigned_employee_id'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE ord_order ADD COLUMN assigned_employee_id int NULL")
                logger.info('Added ord_order.assigned_employee_id column')

            # 处理外键约束 - 需要先删除外键，修改列，再重新添加
            fk_tables = [
                ('ord_ordermember', 'ord_ordermember_employee_id_fk'),
                ('ord_ordercomment', 'ord_ordercomment_employee_id_fk'),
                ('fin_transaction', 'fin_transaction_employee_id_fk'),
                ('fin_settlement_detail', 'fin_settlement_detail_employee_id_fk'),
                ('fin_salary', 'fin_salary_employee_id_fk'),
                ('fin_withdraw', 'fin_withdraw_employee_id_fk'),
            ]
            
            for table, fk_name in fk_tables:
                try:
                    # 检查列是否需要修改
                    cursor.execute(f"""
                        SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' AND COLUMN_NAME = 'employee_id'
                    """)
                    result = cursor.fetchone()
                    if result and result[0] == 'NO':
                        # 尝试删除外键
                        try:
                            cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {fk_name}")
                        except Exception:
                            # 外键名可能不同，尝试查找并删除
                            try:
                                cursor.execute(f"""
                                    SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
                                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' 
                                    AND COLUMN_NAME = 'employee_id' AND REFERENCED_TABLE_NAME IS NOT NULL
                                """)
                                fk = cursor.fetchone()
                                if fk:
                                    cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {fk[0]}")
                            except Exception:
                                pass
                        # 修改列允许 NULL
                        cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN employee_id int NULL")
                        # 重新添加外键
                        try:
                            cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT {fk_name} FOREIGN KEY (employee_id) REFERENCES emp_employee(id) ON DELETE SET NULL")
                        except Exception:
                            pass
                        logger.info(f'{table}.employee_id set to NULL')

        except Exception as e:
            logger.error(f'Failed to update columns via SQL: {e}')
        
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
