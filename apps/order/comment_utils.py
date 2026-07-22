import logging

from django.db import IntegrityError, connection

from .models import OrderComment

logger = logging.getLogger(__name__)


def drop_legacy_order_comment_order_unique():
    if connection.vendor != 'mysql':
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT INDEX_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ord_order_comment'
              AND NON_UNIQUE = 0
              AND INDEX_NAME <> 'PRIMARY'
            GROUP BY INDEX_NAME
            HAVING COUNT(*) = 1
               AND MAX(CASE WHEN COLUMN_NAME = 'order_id' THEN 1 ELSE 0 END) = 1
            """
        )
        index_names = [row[0] for row in cursor.fetchall()]
        for index_name in index_names:
            try:
                # MySQL InnoDB requires an index on FK columns.
                # Add a non-unique index first to satisfy the FK constraint,
                # then safely drop the unique one.
                cursor.execute(
                    "ALTER TABLE ord_order_comment ADD INDEX `idx_order_id_nu` (`order_id`)"
                )
            except Exception:
                pass  # index may already exist
            try:
                cursor.execute(f"ALTER TABLE ord_order_comment DROP INDEX `{index_name}`")
                logger.warning("Dropped legacy unique index %s on ord_order_comment.order_id", index_name)
            except Exception as e:
                logger.warning("Failed to drop legacy unique index %s: %s", index_name, e)


def create_order_comment_with_retry(**kwargs):
    try:
        return OrderComment.objects.create(**kwargs)
    except IntegrityError as exc:
        if 'order_id' not in str(exc):
            raise
        try:
            drop_legacy_order_comment_order_unique()
        except Exception:
            pass
        return OrderComment.objects.create(**kwargs)
