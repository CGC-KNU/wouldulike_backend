"""슈퍼크리스피(298) 제휴 복구 — CloudSQL restaurants_affiliate·benefit 정리."""

from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.super_crispy_restore import restore_super_crispy_affiliate
    from coupons.festival_jungdunbam import resolve_cloudsql_alias

    restore_super_crispy_affiliate(
        db_alias=resolve_cloudsql_alias(),
        dry_run=False,
        reset_pin=True,
        pin=None,
    )


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0079_activate_summer_event_app_open_daily"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
