from datetime import datetime, timezone

from django.db import migrations


def activate_midterm_event_app_open(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    # 2026-04-15 00:00:00 ~ 2026-04-15 23:59:59 (KST)
    # UTC 저장값: 2026-04-14 15:00:00 ~ 2026-04-15 14:59:59
    Campaign.objects.update_or_create(
        code="MIDTERM_EVENT_APP_OPEN",
        defaults={
            "name": "중간고사 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": True,
            "start_at": datetime(2026, 4, 14, 15, 0, 0, tzinfo=timezone.utc),
            "end_at": datetime(2026, 4, 15, 14, 59, 59, tzinfo=timezone.utc),
            "rules_json": {"trigger": "APP_OPEN"},
        },
    )


def revert_midterm_event_app_open(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    # 원복 시에는 캠페인을 비활성화하고 기간만 제거 (데이터 삭제는 피함)
    Campaign.objects.filter(code="MIDTERM_EVENT_APP_OPEN").update(
        active=False,
        start_at=None,
        end_at=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0046_fix_date_event_coupon_expiry_to_20260412"),
    ]

    operations = [
        migrations.RunPython(activate_midterm_event_app_open, revert_midterm_event_app_open),
    ]

