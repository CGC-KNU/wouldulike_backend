"""
0054가 default DB에만 반영되고 앱은 cloudsql 에서 restaurants_affiliate 를 읽는 경우를 보정.
"""
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
        ("coupons", "0055_set_jungdunbam_festival_pin_0629"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
