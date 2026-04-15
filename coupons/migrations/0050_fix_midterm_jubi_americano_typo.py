from __future__ import annotations

from django.db import migrations


FROM_TEXT = "아메라키노"
TO_TEXT = "아메리카노"
MIDTERM_COUPON_TYPE_CODE = "MIDTERM_EVENT_SPECIAL"
JUBI_RESTAURANT_ID = 144


def _replace_typo(value):
    if isinstance(value, str):
        return value.replace(FROM_TEXT, TO_TEXT)
    if isinstance(value, list):
        return [_replace_typo(v) for v in value]
    if isinstance(value, dict):
        return {k: _replace_typo(v) for k, v in value.items()}
    return value


def forward(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    Coupon = apps.get_model("coupons", "Coupon")

    try:
        midterm_type = CouponType.objects.get(code=MIDTERM_COUPON_TYPE_CODE)
    except CouponType.DoesNotExist:
        return

    # 1) 발급 원본(식당별 혜택) 문구 수정
    qs = RestaurantCouponBenefit.objects.filter(
        coupon_type=midterm_type,
        restaurant_id=JUBI_RESTAURANT_ID,
        title__contains=FROM_TEXT,
    )
    for benefit in qs.iterator():
        benefit.title = benefit.title.replace(FROM_TEXT, TO_TEXT)
        benefit.save(update_fields=["title", "updated_at"])

    # 2) 이미 발급된 쿠폰 스냅샷(benefit_snapshot) 문구 수정
    coupon_qs = Coupon.objects.filter(
        coupon_type=midterm_type,
        restaurant_id=JUBI_RESTAURANT_ID,
        benefit_snapshot__isnull=False,
    )
    for c in coupon_qs.iterator():
        snap = c.benefit_snapshot or {}
        new_snap = _replace_typo(snap)
        if new_snap != snap:
            c.benefit_snapshot = new_snap
            c.save(update_fields=["benefit_snapshot"])


def backward(apps, schema_editor):
    # 데이터 보정 마이그레이션은 원복(noop)이 안전합니다.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0049_add_midterm_daily_codes_campaign_20260415_20260424"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

