"""우주라이크 X 정든밤(299)·구 ID(298): is_affiliate=FALSE — 제휴식당 목록·넘기기에서 제외."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import (
        LEGACY_FESTIVAL_RESTAURANT_ID,
        RESTAURANT_ID,
        ensure_jungdunbam_festival_data,
        resolve_cloudsql_alias,
    )
    from django.db import connections

    alias = resolve_cloudsql_alias()
    ensure_jungdunbam_festival_data(db_alias=alias)

    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurants_affiliate
            SET is_affiliate = FALSE
            WHERE restaurant_id IN (%s, %s)
            """,
            [RESTAURANT_ID, LEGACY_FESTIVAL_RESTAURANT_ID],
        )


def backward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import (
        LEGACY_FESTIVAL_RESTAURANT_ID,
        RESTAURANT_ID,
        resolve_cloudsql_alias,
    )
    from django.db import connections

    alias = resolve_cloudsql_alias()
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurants_affiliate
            SET is_affiliate = TRUE
            WHERE restaurant_id = %s
            """,
            [RESTAURANT_ID],
        )
        cursor.execute(
            """
            UPDATE restaurants_affiliate
            SET is_affiliate = FALSE
            WHERE restaurant_id = %s
            """,
            [LEGACY_FESTIVAL_RESTAURANT_ID],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0076_sync_pub_jujeom_benefits_all_targets"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
