"""월드컵 기획전 앱 접속 일일 랜덤 1장 발급 캠페인 활성화 (2026-06-08 ~ 2026-06-21 KST)."""

from datetime import datetime, timezone

from django.db import migrations


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    # 2026-06-08 00:00:00 ~ 2026-06-21 23:59:59 (KST)
    world_cup_start = datetime(2026, 6, 7, 15, 0, 0, tzinfo=timezone.utc)
    world_cup_end = datetime(2026, 6, 21, 14, 59, 59, tzinfo=timezone.utc)

    Campaign.objects.filter(code="SUMMER_EVENT_APP_OPEN").update(
        active=False,
        rules_json={"trigger": "APP_OPEN"},
    )
    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        active=True,
        start_at=world_cup_start,
        end_at=world_cup_end,
        rules_json={"trigger": "APP_OPEN", "mode": "DAILY_RANDOM_ONE"},
    )


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        active=False,
        rules_json={"trigger": "APP_OPEN"},
    )
    Campaign.objects.filter(code="SUMMER_EVENT_APP_OPEN").update(
        active=True,
        rules_json={"trigger": "APP_OPEN", "mode": "DAILY_RANDOM_ONE"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0085_add_super_crispy_s3_images"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
