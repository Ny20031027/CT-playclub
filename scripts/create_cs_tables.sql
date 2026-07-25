-- 客服欢迎语配置表
CREATE TABLE IF NOT EXISTS `sys_cs_welcome_config` (
    `id` bigint NOT NULL AUTO_INCREMENT,
    `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
    `welcome_text` longtext NOT NULL DEFAULT '',
    `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='客服欢迎语配置';

-- 客服关键词自动回复规则表
CREATE TABLE IF NOT EXISTS `sys_cs_keyword_rule` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='客服关键词规则';

-- 服务项目表
CREATE TABLE IF NOT EXISTS `sys_service_item` (
    `id` bigint NOT NULL AUTO_INCREMENT,
    `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `is_deleted` tinyint(1) NOT NULL DEFAULT 0,
    `name` varchar(100) NOT NULL,
    `category` varchar(50) NOT NULL DEFAULT '',
    `unit_price` decimal(10,2) NOT NULL DEFAULT 0,
    `unit` varchar(20) NOT NULL DEFAULT 'hour',
    `description` varchar(500) NOT NULL DEFAULT '',
    `sort` int NOT NULL DEFAULT 0,
    `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='服务项目';
