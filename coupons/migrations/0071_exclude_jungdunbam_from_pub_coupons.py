"""298 축제 주막: 수요일·주점 이벤트 풀 제외 및 타 benefit 비활성화."""

from django.db import migrations


def apply(apps, schema_editor):
    from coupons.festival_jungdunbam import ensure_jungdunbam_festival_data, resolve_cloudsql_alias
    from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data

    alias = resolve_cloudsql_alias()
    ensure_jungdunbam_festival_data(db_alias=alias)
    ensure_pub_jujeom_event_data(db_alias=alias)


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0070_jungdunbam_stamp_plain_display"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
