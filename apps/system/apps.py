from django.apps import AppConfig


class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system'
    verbose_name = '系统设置'

    def ready(self):
        self._auto_create_cs_tables()

    def _auto_create_cs_tables(self):
        from django.db import connection
        stmts = [
            """CREATE TABLE IF NOT EXISTS `sys_cs_welcome_config` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
                `welcome_text` longtext NOT NULL DEFAULT '',
                `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci""",
            """CREATE TABLE IF NOT EXISTS `sys_cs_keyword_rule` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
                `keyword` varchar(200) NOT NULL,
                `reply_text` longtext NOT NULL,
                `match_type` varchar(20) NOT NULL DEFAULT 'contains',
                `sort` int NOT NULL DEFAULT 0,
                `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
                PRIMARY KEY (`id`),
                KEY `idx_keyword` (`keyword`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci""",
            """CREATE TABLE IF NOT EXISTS `sys_service_item` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
                `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
                `name` varchar(100) NOT NULL,
                `category` varchar(50) NOT NULL DEFAULT '',
                `unit_price` decimal(10,2) NOT NULL DEFAULT 0,
                `description` varchar(500) NOT NULL DEFAULT '',
                `sort` int NOT NULL DEFAULT 0,
                `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci""",
        ]
        try:
            with connection.cursor() as cursor:
                for stmt in stmts:
                    try:
                        cursor.execute(stmt)
                    except Exception:
                        pass
        except Exception:
            pass
