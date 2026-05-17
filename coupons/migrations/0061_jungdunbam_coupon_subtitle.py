"""축제 주막 쿠폰 subtitle → [경북대 80주년 축제 🎉]."""
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
        ("coupons", "0060_jungdunbam_wed_coupon_same_day_expiry"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
