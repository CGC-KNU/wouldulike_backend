"""우주라이크 X 정든밤(298): is_affiliate=FALSE — 앱 식당 목록 비노출."""
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
        ("coupons", "0061_jungdunbam_coupon_subtitle"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
