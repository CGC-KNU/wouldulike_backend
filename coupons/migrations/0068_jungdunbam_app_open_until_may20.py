"""정든밤 축제: 수요일 제한 제거, 5/20 23:59(KST)까지 앱 접속 발급·만료."""
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
        ("coupons", "0067_jungdunbam_restore_affiliate"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
