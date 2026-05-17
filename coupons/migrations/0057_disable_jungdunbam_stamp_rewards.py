"""축제 주막(298) 스탬프 규칙 제거 — 앱에는 promotions·notes 로 안내."""
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
        ("coupons", "0056_ensure_jungdunbam_festival_on_cloudsql"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
