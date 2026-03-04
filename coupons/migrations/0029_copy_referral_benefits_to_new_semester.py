from django.db import migrations


def copy_referral_benefits_to_new_semester(apps, schema_editor):
    """REFERRAL_BONUS_REFEREE의 식당별 쿠폰 내용을 NEW_SEMESTER_SPECIAL로 복사합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    try:
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
        new_semester_type = CouponType.objects.get(code="NEW_SEMESTER_SPECIAL")
    except CouponType.DoesNotExist:
        return

    referral_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=referral_type,
        active=True,
    )

    for benefit in referral_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=new_semester_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": "신학기 추천코드 이벤트",
                "benefit_json": benefit.benefit_json,
                "active": benefit.active,
            },
        )


def remove_new_semester_benefits(apps, schema_editor):
    """NEW_SEMESTER_SPECIAL의 식당별 쿠폰 내용을 삭제합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    try:
        new_semester_type = CouponType.objects.get(code="NEW_SEMESTER_SPECIAL")
    except CouponType.DoesNotExist:
        return

    RestaurantCouponBenefit.objects.filter(coupon_type=new_semester_type).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0028_add_new_semester_event"),
    ]

    operations = [
        migrations.RunPython(copy_referral_benefits_to_new_semester, remove_new_semester_benefits),
    ]
