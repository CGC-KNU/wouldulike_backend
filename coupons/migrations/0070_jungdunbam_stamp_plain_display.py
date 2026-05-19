"""축제 주막(298): 스탬프 안내 plain 표시 필드·레거시 템플릿용 title."""

from django.db import migrations


def apply(apps, schema_editor):
    from coupons.festival_jungdunbam import ensure_jungdunbam_festival_data, resolve_cloudsql_alias

    ensure_jungdunbam_festival_data(db_alias=resolve_cloudsql_alias())


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0069_jungdunbam_stamp_display_rewards"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
