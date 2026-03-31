from datetime import datetime, timezone

from django.db import migrations


GLOBAL_STAMP_EXPIRY = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)


def apply_stamp_expiry_global(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Coupon = apps.get_model("coupons", "Coupon")

    stamp_types = CouponType.objects.filter(code__startswith="STAMP_REWARD")
    stamp_type_codes = list(stamp_types.values_list("code", flat=True))

    # 이후 발급분이 valid_days를 타지 않도록 정리
    stamp_types.update(valid_days=0)

    # 기존 발급된 스탬프 보상 쿠폰 만료일도 글로벌 만료일로 정렬
    Coupon.objects.filter(coupon_type__code__in=stamp_type_codes).update(
        expires_at=GLOBAL_STAMP_EXPIRY
    )


def noop_revert(apps, schema_editor):
    # 데이터 복구 기준이 불명확하여 롤백은 no-op
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0039_update_date_event_subtitle"),
    ]

    operations = [
        migrations.RunPython(apply_stamp_expiry_global, noop_revert),
    ]
