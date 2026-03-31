from django.db import migrations, models
from django.db.utils import OperationalError, ProgrammingError


def add_description_column_if_table_exists(apps, schema_editor):
    """테이블이 존재하는 경우에만 description 컬럼을 추가합니다."""
    conn = schema_editor.connection
    # SQLite 등에서는 information_schema / IF NOT EXISTS 문법이 달라질 수 있으므로 스킵
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
            table_exists = cursor.fetchone()[0]
            if table_exists:
                cursor.execute(
                    """
                    ALTER TABLE restaurants_affiliate
                    ADD COLUMN IF NOT EXISTS description TEXT;
                    """
                )
        except (OperationalError, ProgrammingError):
            # DB 종류/권한/스키마 차이로 실패할 수 있으니 안전하게 스킵
            return


def remove_description_column_if_table_exists(apps, schema_editor):
    """테이블이 존재하는 경우에만 description 컬럼을 제거합니다."""
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
            table_exists = cursor.fetchone()[0]
            if table_exists:
                cursor.execute(
                    """
                    ALTER TABLE restaurants_affiliate
                    DROP COLUMN IF EXISTS description;
                    """
                )
        except (OperationalError, ProgrammingError):
            return


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0004_affiliaterestaurant"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_description_column_if_table_exists,
                    remove_description_column_if_table_exists,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="affiliaterestaurant",
                    name="description",
                    field=models.TextField(null=True, blank=True),
                ),
            ],
        ),
    ]
