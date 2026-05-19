"""restaurants_affiliate(CloudSQL) 스키마·연결 헬퍼."""

from django.db import connections
from django.db.utils import OperationalError, ProgrammingError

AFFILIATE_TABLE = "restaurants_affiliate"
SUMMARY_COLUMN = "coupon_benefits_summary"


def affiliate_column_exists(conn, column: str = SUMMARY_COLUMN) -> bool:
    with conn.cursor() as cursor:
        if conn.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = %s
                LIMIT 1
                """,
                [AFFILIATE_TABLE, column],
            )
            return cursor.fetchone() is not None
        columns = {
            col.name
            for col in conn.introspection.get_table_description(cursor, AFFILIATE_TABLE)
        }
        return column in columns


def ensure_affiliate_summary_column(conn) -> bool:
    """
    coupon_benefits_summary 컬럼이 없으면 추가.
    Returns True if column exists (already or just added).
    """
    if affiliate_column_exists(conn):
        return True
    if conn.vendor == "sqlite":
        return False

    with conn.cursor() as cursor:
        try:
            cursor.execute(
                f"""
                ALTER TABLE {AFFILIATE_TABLE}
                ADD COLUMN IF NOT EXISTS {SUMMARY_COLUMN} JSONB;
                """
            )
        except (OperationalError, ProgrammingError):
            return False
    return affiliate_column_exists(conn)


def resolve_affiliate_db_alias(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    from django.db import router
    from restaurants.models import AffiliateRestaurant

    return router.db_for_read(AffiliateRestaurant)
