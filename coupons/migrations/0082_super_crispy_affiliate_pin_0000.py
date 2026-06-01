"""
슈퍼크리스피(298) 제휴 보정 (레거시 — PIN 은 env 마이그레이션 0083 에서만).

0080_restore 가 이미 적용된 환경용 idempotent 제휴 복구.
"""

from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import resolve_cloudsql_alias
    from coupons.super_crispy_restore import restore_super_crispy_affiliate

    restore_super_crispy_affiliate(
        db_alias=resolve_cloudsql_alias(),
        dry_run=False,
        reset_pin=False,
        pin=None,
    )


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0081_update_summer_event_subtitle"),
        ("coupons", "0080_restore_super_crispy_affiliate_298"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
