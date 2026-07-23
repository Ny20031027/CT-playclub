import os
import threading
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = '公共模块'

    def ready(self):
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

        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SELECT GET_LOCK('playclub_auto_migrate', 0)")
                locked = cursor.fetchone()[0] == 1
            if not locked:
                logger.info('Auto migrate skipped: another worker is running it')
                return

            try:
                self._fix_columns(logger, connections)
                call_command('migrate', verbosity=1, interactive=False)
                logger.info('Auto migrate completed')
            finally:
                try:
                    with connections['default'].cursor() as cursor:
                        cursor.execute("SELECT RELEASE_LOCK('playclub_auto_migrate')")
                except Exception:
                    pass
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
            try:
                cursor.execute("SHOW INDEX FROM ord_order_comment WHERE Column_name = 'order_id' AND Non_unique = 0 AND Key_name != 'PRIMARY'")
                indexes = cursor.fetchall()
                for idx in indexes:
                    idx_name = idx[2]  # Key_name is at index 2
                    cursor.execute(f"ALTER TABLE ord_order_comment DROP INDEX `{idx_name}`")
                    logger.info(f'Dropped index {idx_name} on ord_order_comment.order_id')
            except Exception as e:
                logger.warning(f'Failed to drop unique index: {e}')

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
                    fk_name = None
                    if col == 'employee_id':
                        cursor.execute("""
                            SELECT CONSTRAINT_NAME
                            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'ord_order_comment'
                              AND COLUMN_NAME = 'employee_id'
                              AND REFERENCED_TABLE_NAME IS NOT NULL
                            LIMIT 1
                        """)
                        fk_row = cursor.fetchone()
                        fk_name = fk_row[0] if fk_row else None
                        if fk_name:
                            cursor.execute(f"ALTER TABLE ord_order_comment DROP FOREIGN KEY `{fk_name}`")
                    cursor.execute(f"ALTER TABLE ord_order_comment MODIFY COLUMN {col} int NULL")
                    if col == 'employee_id':
                        cursor.execute(
                            "ALTER TABLE ord_order_comment ADD CONSTRAINT `ord_order_comment_employee_id_5737587d_fk_emp_employee_id` "
                            "FOREIGN KEY (`employee_id`) REFERENCES `emp_employee` (`id`) ON DELETE SET NULL"
                        )
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

            # 创建售后工单表（如果不存在）
            cursor.execute(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ord_support_ticket'"
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "CREATE TABLE ord_support_ticket ("
                    "id bigint AUTO_INCREMENT PRIMARY KEY,"
                    "created_at datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),"
                    "updated_at datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),"
                    "is_deleted tinyint(1) NOT NULL DEFAULT 0,"
                    "ticket_no varchar(50) NOT NULL UNIQUE,"
                    "title varchar(200) NOT NULL,"
                    "description longtext NOT NULL,"
                    "status varchar(20) NOT NULL DEFAULT 'open',"
                    "order_snapshot longtext NULL,"
                    "handle_remark longtext NOT NULL,"
                    "closed_at datetime(6) NULL,"
                    "order_id bigint NOT NULL,"
                    "customer_id bigint NOT NULL,"
                    "employee_id bigint NULL,"
                    "handler_id bigint NULL"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
                logger.info('Created ord_support_ticket table')

            # 添加 cs_message.ticket_id 列
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cs_message' AND COLUMN_NAME = 'ticket_id'
            """)
            ticket_column_missing = cursor.fetchone()[0] == 0
            if ticket_column_missing:
                cursor.execute("ALTER TABLE cs_message ADD COLUMN ticket_id bigint NULL")
                logger.info('Added cs_message.ticket_id column')
            cursor.execute("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'cs_message'
                  AND COLUMN_NAME = 'ticket_id'
                  AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE cs_message ADD FOREIGN KEY (ticket_id) REFERENCES ord_support_ticket(id) ON DELETE SET NULL")
                logger.info('Added cs_message.ticket_id foreign key')

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
