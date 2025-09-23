from datetime import datetime, timezone as dt_timezone
from django.db import migrations


def set_coupon_expiry(apps, schema_editor):
    Coupon = apps.get_model("coupons", "Coupon")
    target = datetime(2026, 1, 31, 23, 59, 59, tzinfo=dt_timezone.utc)
    Coupon.objects.update(expires_at=target)


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0003_merchantpin_alter_coupon_user_alter_invitecode_user_and_more"),
    ]

    operations = [
        migrations.RunPython(set_coupon_expiry, migrations.RunPython.noop),
    ]
