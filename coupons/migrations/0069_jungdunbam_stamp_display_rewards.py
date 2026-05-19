"""축제 주막(298): 스탬프 카드 5·10 구간 + '적립·보상 없음' 안내 표시."""

from django.db import migrations


def apply(apps, schema_editor):
    from coupons.festival_jungdunbam import ensure_jungdunbam_festival_data, resolve_cloudsql_alias

    ensure_jungdunbam_festival_data(db_alias=resolve_cloudsql_alias())


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0068_jungdunbam_app_open_until_may20"),
    ]

    operations = [
        migrations.RunPython(apply, migrations.RunPython.noop),
    ]
