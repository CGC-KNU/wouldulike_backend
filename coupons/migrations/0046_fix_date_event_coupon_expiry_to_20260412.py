from datetime import datetime, timezone as dt_timezone

from django.db import migrations


DATE_COUPON_TYPE_CODE = "DATE_EVENT_SPECIAL"
DATE_CAMPAIGN_CODE = "DATE_EVENT_APP_OPEN"

# 2026-04-12 23:59:59 KST = 2026-04-12 14:59:59 UTC
TARGET_EXPIRES_AT = datetime(2026, 4, 12, 14, 59, 59, tzinfo=dt_timezone.utc)


def forward(apps, schema_editor):
    Coupon = apps.get_model("coupons", "Coupon")
    Coupon.objects.filter(coupon_type__code=DATE_COUPON_TYPE_CODE).update(
        expires_at=TARGET_EXPIRES_AT
    )
    Coupon.objects.filter(campaign__code=DATE_CAMPAIGN_CODE).update(
        expires_at=TARGET_EXPIRES_AT
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0045_dedupe_full_affiliate_one_row_per_restaurant"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]

