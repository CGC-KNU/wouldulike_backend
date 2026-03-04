from django.db import migrations


def update_new_semester_title(apps, schema_editor):
    """NEW_SEMESTER_SPECIAL CouponType 및 RestaurantCouponBenefit title/subtitle을 [개강 응원 쿠폰 💪]로 업데이트."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="NEW_SEMESTER_SPECIAL").update(
        title="[개강 응원 쿠폰 💪]"
    )
    RestaurantCouponBenefit.objects.filter(
        coupon_type__code="NEW_SEMESTER_SPECIAL"
    ).update(subtitle="[개강 응원 쿠폰 💪]")


def revert_new_semester_title(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="NEW_SEMESTER_SPECIAL").update(
        title="신학기 추천코드 이벤트"
    )
    RestaurantCouponBenefit.objects.filter(
        coupon_type__code="NEW_SEMESTER_SPECIAL"
    ).update(subtitle="신학기 추천코드 이벤트")


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0029_copy_referral_benefits_to_new_semester"),
    ]

    operations = [
        migrations.RunPython(update_new_semester_title, revert_new_semester_title),
    ]
