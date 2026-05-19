"""축제 주막 restaurant_id 298 → 299 이전 (구 ID와 쿠폰 데이터 겹침 방지)."""

from django.db import migrations


def apply(apps, schema_editor):
    from coupons.festival_jungdunbam import (
        reassign_festival_restaurant_id,
        resolve_cloudsql_alias,
    )
    from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data

    alias = resolve_cloudsql_alias()
    reassign_festival_restaurant_id(db_alias=alias)
    ensure_pub_jujeom_event_data(db_alias=alias)


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0071_exclude_jungdunbam_from_pub_coupons"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
