from django.db import migrations


NEW_SUBTITLE = "[데이트 캠페인 쿠폰 💕]"
OLD_SUBTITLE = "[데이트 기획전 쿠폰]"


def apply_subtitle_update(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign = apps.get_model("coupons", "Campaign")
    Coupon = apps.get_model("coupons", "Coupon")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    ct = CouponType.objects.filter(code="DATE_EVENT_SPECIAL").first()
    if not ct:
        return

    RestaurantCouponBenefit.objects.filter(coupon_type=ct).update(subtitle=NEW_SUBTITLE)

    camp = Campaign.objects.filter(code="DATE_EVENT_APP_OPEN").first()
    if not camp:
        return

    coupons = Coupon.objects.filter(coupon_type=ct, campaign=camp)
    for coupon in coupons.iterator():
        snapshot = coupon.benefit_snapshot or {}
        snapshot["subtitle"] = NEW_SUBTITLE
        coupon.benefit_snapshot = snapshot
        coupon.save(update_fields=["benefit_snapshot"])


def revert_subtitle_update(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign = apps.get_model("coupons", "Campaign")
    Coupon = apps.get_model("coupons", "Coupon")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    ct = CouponType.objects.filter(code="DATE_EVENT_SPECIAL").first()
    if not ct:
        return

    RestaurantCouponBenefit.objects.filter(coupon_type=ct).update(subtitle=OLD_SUBTITLE)

    camp = Campaign.objects.filter(code="DATE_EVENT_APP_OPEN").first()
    if not camp:
        return

    coupons = Coupon.objects.filter(coupon_type=ct, campaign=camp)
    for coupon in coupons.iterator():
        snapshot = coupon.benefit_snapshot or {}
        snapshot["subtitle"] = OLD_SUBTITLE
        coupon.benefit_snapshot = snapshot
        coupon.save(update_fields=["benefit_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0038_add_date_midterm_coupon_types"),
    ]

    operations = [
        migrations.RunPython(apply_subtitle_update, revert_subtitle_update),
    ]
