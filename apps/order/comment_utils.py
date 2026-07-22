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
            cursor.execute(f"ALTER TABLE ord_order_comment DROP INDEX `{index_name}`")
            logger.warning("Dropped legacy unique index %s on ord_order_comment.order_id", index_name)


def create_order_comment_with_retry(**kwargs):
    try:
        return OrderComment.objects.create(**kwargs)
    except IntegrityError as exc:
        if 'order_id' not in str(exc):
            raise
        drop_legacy_order_comment_order_unique()
        return OrderComment.objects.create(**kwargs)
