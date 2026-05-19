from django.db.utils import OperationalError, ProgrammingError


def add_coupon_benefits_summary_column_if_table_exists(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "sqlite":
        return

    with conn.cursor() as cursor:
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'restaurants_affiliate'
                );
                """
            )
            if not cursor.fetchone()[0]:
                return
            cursor.execute(
                """
                ALTER TABLE restaurants_affiliate
                ADD COLUMN IF NOT EXISTS coupon_benefits_summary JSONB;
                """
            )
        except (OperationalError, ProgrammingError):
            return


def remove_coupon_benefits_summary_column_if_table_exists(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "sqlite":
        return

    with conn.cursor() as cursor:
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = 'restaurants_affiliate'
                );
                """
            )
            if not cursor.fetchone()[0]:
                return
            cursor.execute(
                """
                ALTER TABLE restaurants_affiliate
                DROP COLUMN IF EXISTS coupon_benefits_summary;
                """
            )
        except (OperationalError, ProgrammingError):
            return
