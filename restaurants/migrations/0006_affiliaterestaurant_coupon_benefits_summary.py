from django.db import migrations, models
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


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_coupon_benefits_summary_column_if_table_exists,
                    remove_coupon_benefits_summary_column_if_table_exists,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="affiliaterestaurant",
                    name="coupon_benefits_summary",
                    field=models.JSONField(null=True, blank=True),
                ),
            ],
        ),
    ]
