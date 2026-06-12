from django.db import migrations


WORLD_CUP_COUPON_TYPE_CODE = "WORLD_CUP_EVENT_SPECIAL"
OLD_SUBTITLE = "[월드컵 기획전 쿠폰 ⚽]"
NEW_SUBTITLE = "[월드컵 응원 쿠폰 ⚽🔥]"


def apply_subtitle_update(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Coupon = apps.get_model("coupons", "Coupon")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    ct = CouponType.objects.filter(code=WORLD_CUP_COUPON_TYPE_CODE).first()
    if not ct:
        return

    CouponType.objects.filter(pk=ct.pk).update(title=NEW_SUBTITLE)
    RestaurantCouponBenefit.objects.filter(coupon_type=ct).update(subtitle=NEW_SUBTITLE)

    coupons = Coupon.objects.filter(coupon_type=ct)
    for coupon in coupons.iterator():
        snapshot = dict(coupon.benefit_snapshot or {})
        if snapshot.get("subtitle") == OLD_SUBTITLE:
            snapshot["subtitle"] = NEW_SUBTITLE
        if snapshot.get("coupon_type_title") == OLD_SUBTITLE:
            snapshot["coupon_type_title"] = NEW_SUBTITLE
        if snapshot.get("title") == OLD_SUBTITLE:
            snapshot["title"] = NEW_SUBTITLE
        coupon.benefit_snapshot = snapshot
        coupon.save(update_fields=["benefit_snapshot"])


def revert_subtitle_update(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Coupon = apps.get_model("coupons", "Coupon")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    ct = CouponType.objects.filter(code=WORLD_CUP_COUPON_TYPE_CODE).first()
    if not ct:
        return

    CouponType.objects.filter(pk=ct.pk).update(title=OLD_SUBTITLE)
    RestaurantCouponBenefit.objects.filter(coupon_type=ct).update(subtitle=OLD_SUBTITLE)

    coupons = Coupon.objects.filter(coupon_type=ct)
    for coupon in coupons.iterator():
        snapshot = dict(coupon.benefit_snapshot or {})
        if snapshot.get("subtitle") == NEW_SUBTITLE:
            snapshot["subtitle"] = OLD_SUBTITLE
        if snapshot.get("coupon_type_title") == NEW_SUBTITLE:
            snapshot["coupon_type_title"] = OLD_SUBTITLE
        if snapshot.get("title") == NEW_SUBTITLE:
            snapshot["title"] = OLD_SUBTITLE
        coupon.benefit_snapshot = snapshot
        coupon.save(update_fields=["benefit_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0086_activate_world_cup_event_app_open_daily"),
    ]

    operations = [
        migrations.RunPython(apply_subtitle_update, revert_subtitle_update),
    ]
