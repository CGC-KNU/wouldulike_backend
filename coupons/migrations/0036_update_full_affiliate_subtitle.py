from django.db import migrations


def update_full_affiliate_subtitle(apps, schema_editor):
    """FULL_AFFILIATE_SPECIAL 쿠폰의 subtitle을 [🎈가두모집 쿠폰팩🎈]로 변경."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    try:
        full_affiliate_type = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
    except CouponType.DoesNotExist:
        return

    RestaurantCouponBenefit.objects.filter(coupon_type=full_affiliate_type).update(
        subtitle="[🎈가두모집 쿠폰팩🎈]"
    )


def noop_revert(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0035_add_app_open_mon_wed_event"),
    ]

    operations = [
        migrations.RunPython(update_full_affiliate_subtitle, noop_revert),
    ]
