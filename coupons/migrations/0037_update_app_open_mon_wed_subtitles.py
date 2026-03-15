from django.db import migrations


def update_app_open_mon_wed_subtitles(apps, schema_editor):
    """APP_OPEN_MON: [월요병 치료 쿠폰 💊], APP_OPEN_WED: [술요일 쿠폰 🍺]"""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    for code, subtitle in [
        ("APP_OPEN_MON", "[월요병 치료 쿠폰 💊]"),
        ("APP_OPEN_WED", "[술요일 쿠폰 🍺]"),
    ]:
        try:
            ct = CouponType.objects.get(code=code)
            RestaurantCouponBenefit.objects.filter(coupon_type=ct).update(subtitle=subtitle)
        except CouponType.DoesNotExist:
            pass


def noop_revert(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0036_update_full_affiliate_subtitle"),
    ]

    operations = [
        migrations.RunPython(update_app_open_mon_wed_subtitles, noop_revert),
    ]
