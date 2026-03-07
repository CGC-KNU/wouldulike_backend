from django.db import migrations


def update_knulike_title(apps, schema_editor):
    """KNULIKE CouponType 및 RestaurantCouponBenefit title/subtitle을 [학생회 제휴 쿠폰 🤝]로 업데이트."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="KNULIKE").update(
        title="[학생회 제휴 쿠폰 🤝]"
    )
    RestaurantCouponBenefit.objects.filter(
        coupon_type__code="KNULIKE"
    ).update(title="[학생회 제휴 쿠폰 🤝]", subtitle="[학생회 제휴 쿠폰 🤝]")


def revert_knulike_title(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="KNULIKE").update(title="[KNULIKE 쿠폰]")
    RestaurantCouponBenefit.objects.filter(
        coupon_type__code="KNULIKE"
    ).update(title="[KNULIKE 쿠폰]", subtitle="[KNULIKE 쿠폰]")


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0031_add_knulike_event"),
    ]

    operations = [
        migrations.RunPython(update_knulike_title, revert_knulike_title),
    ]
