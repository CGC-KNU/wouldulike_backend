"""슈퍼크리스피(298): 299에 이전된 쿠폰·스탬프 설정 복구."""

from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import resolve_cloudsql_alias
    from coupons.super_crispy_restore import complete_super_crispy_recovery

    complete_super_crispy_recovery(
        db_alias=resolve_cloudsql_alias(), dry_run=False
    )


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0083_super_crispy_pin_from_env"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
