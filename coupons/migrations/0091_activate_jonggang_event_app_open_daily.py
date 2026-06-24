"""종강 기획전 앱 접속 일일 랜덤 1장 발급 캠페인 활성화 (2026-06-22 ~ 2026-07-07 KST)."""

from datetime import datetime, timezone

from django.db import migrations


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    # 2026-06-22 00:00:00 ~ 2026-07-07 23:59:59 (KST)
    jonggang_start = datetime(2026, 6, 21, 15, 0, 0, tzinfo=timezone.utc)
    jonggang_end = datetime(2026, 7, 7, 14, 59, 59, tzinfo=timezone.utc)

    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        active=False,
        rules_json={"trigger": "APP_OPEN"},
    )
    Campaign.objects.filter(code="JONGGANG_EVENT_APP_OPEN").update(
        active=True,
        start_at=jonggang_start,
        end_at=jonggang_end,
        rules_json={"trigger": "APP_OPEN", "mode": "DAILY_RANDOM_ONE"},
    )


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    Campaign.objects.filter(code="JONGGANG_EVENT_APP_OPEN").update(
        active=False,
        rules_json={"trigger": "APP_OPEN"},
    )
    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        active=True,
        rules_json={
            "trigger": "APP_OPEN",
            "mode": "DAILY_RANDOM_PACK",
            "count": 3,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0090_add_jonggang_event_coupon_types"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
