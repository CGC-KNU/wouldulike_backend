from datetime import datetime, timezone

from django.db import migrations


def add_midterm_daily_codes_campaign(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    # 2026-04-15 00:00:00 ~ 2026-04-24 23:59:59 (KST)
    # UTC 저장값: 2026-04-14 15:00:00 ~ 2026-04-24 14:59:59
    Campaign.objects.update_or_create(
        code="MIDTERM_EVENT_DAILY_CODES",
        defaults={
            "name": "중간고사 캠페인 날짜별 쿠폰코드",
            "type": "FLASH",
            "active": True,
            "start_at": datetime(2026, 4, 14, 15, 0, 0, tzinfo=timezone.utc),
            "end_at": datetime(2026, 4, 24, 14, 59, 59, tzinfo=timezone.utc),
            "rules_json": {"trigger": "COUPON_CODE", "group": "MIDTERM_DAILY"},
        },
    )


def revert_midterm_daily_codes_campaign(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="MIDTERM_EVENT_DAILY_CODES").update(
        active=False,
        start_at=None,
        end_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0048_add_midterm_studylike_campaign_20260414_20260424"),
    ]

    operations = [
        migrations.RunPython(add_midterm_daily_codes_campaign, revert_midterm_daily_codes_campaign),
    ]

