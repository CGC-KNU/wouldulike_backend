"""슈퍼크리스피(298) PIN — SUPER_CRISPY_RESTAURANT_PIN 환경 변수로만 설정 (Git 미포함)."""

from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import resolve_cloudsql_alias
    from coupons.super_crispy_restore import apply_super_crispy_pin_from_env

    apply_super_crispy_pin_from_env(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0082_super_crispy_affiliate_pin_0000"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
