"""축제 주막(298): DB에 남은 스탬프 규칙·STAMP_REWARD benefit 비활성화 재확인."""
from django.db import migrations


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return
    from coupons.festival_jungdunbam import disable_stamp_rewards_for_jungdunbam, resolve_cloudsql_alias

    disable_stamp_rewards_for_jungdunbam(db_alias=resolve_cloudsql_alias())


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0057_disable_jungdunbam_stamp_rewards"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
