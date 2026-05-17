"""축제 주막(298): StampRewardRule에 스탬프 비활성·비고를 DB에 명시 저장."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import (
        ensure_stamp_disabled_rule_for_jungdunbam,
        resolve_cloudsql_alias,
    )

    ensure_stamp_disabled_rule_for_jungdunbam(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0058_jungdunbam_no_legacy_stamp_benefits"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
