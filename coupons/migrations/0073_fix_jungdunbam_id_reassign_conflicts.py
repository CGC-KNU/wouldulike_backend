"""298→299 이전 시 benefit/exclusion unique 충돌 보정 (0072 CloudSQL 실패 복구)."""

from django.db import migrations


def apply(apps, schema_editor):
    from coupons.festival_jungdunbam import reassign_festival_restaurant_id, resolve_cloudsql_alias
    from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data

    alias = resolve_cloudsql_alias()
    reassign_festival_restaurant_id(db_alias=alias)
    ensure_pub_jujeom_event_data(db_alias=alias)


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0072_jungdunbam_festival_restaurant_id_299"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
