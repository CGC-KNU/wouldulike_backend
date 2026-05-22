"""SUMMERLIKE 코드 입력 — 여름맞이 풀 전체 발급 캠페인."""

from datetime import datetime, timezone

from django.db import migrations


SUMMERLIKE_CAMPAIGN_CODE = "SUMMERLIKE_EVENT"


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    # 2026-05-22 00:00:00 ~ 2026-06-07 23:59:59 (KST)
    start_at = datetime(2026, 5, 21, 15, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 6, 7, 14, 59, 59, tzinfo=timezone.utc)

    Campaign.objects.update_or_create(
        code=SUMMERLIKE_CAMPAIGN_CODE,
        defaults={
            "name": "여름맞이 SUMMERLIKE 쿠폰",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {
                "trigger": "COUPON_CODE",
                "code": "SUMMERLIKE",
                "mode": "FULL_POOL",
            },
        },
    )


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code=SUMMERLIKE_CAMPAIGN_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0079_activate_summer_event_app_open_daily"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
