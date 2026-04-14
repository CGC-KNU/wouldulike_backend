from datetime import datetime, timezone

from django.db import migrations


def add_midterm_studylike_campaign(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    # 2026-04-14 00:00:00 ~ 2026-04-24 23:59:59 (KST)
    # UTC 저장값: 2026-04-13 15:00:00 ~ 2026-04-24 14:59:59
    Campaign.objects.update_or_create(
        code="MIDTERM_EVENT_STUDYLIKE",
        defaults={
            "name": "중간고사 기획전 STUDYLIKE 쿠폰",
            "type": "FLASH",
            "active": True,
            "start_at": datetime(2026, 4, 13, 15, 0, 0, tzinfo=timezone.utc),
            "end_at": datetime(2026, 4, 24, 14, 59, 59, tzinfo=timezone.utc),
            "rules_json": {"trigger": "COUPON_CODE", "code": "STUDYLIKE"},
        },
    )


def revert_midterm_studylike_campaign(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="MIDTERM_EVENT_STUDYLIKE").update(
        active=False,
        start_at=None,
        end_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0047_activate_midterm_event_app_open_20260415"),
    ]

    operations = [
        migrations.RunPython(add_midterm_studylike_campaign, revert_midterm_studylike_campaign),
    ]

