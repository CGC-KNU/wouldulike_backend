"""축제 주막 수요일 쿠폰: valid_days=0, DB 시드(만료는 발급 로직에서 수요일 23:59 KST)."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import ensure_jungdunbam_festival_data, resolve_cloudsql_alias

    ensure_jungdunbam_festival_data(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0059_jungdunbam_stamp_rule_in_db"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
