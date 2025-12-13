from django.db import migrations


def copy_referral_benefits_to_final_exam(apps, schema_editor):
    """REFERRAL_BONUS_REFEREE의 식당별 쿠폰 내용을 FINAL_EXAM_SPECIAL로 복사합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    try:
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
    except CouponType.DoesNotExist:
        # 쿠폰 타입이 없으면 스킵
        return
    
    # REFERRAL_BONUS_REFEREE의 식당별 쿠폰 내용 가져오기
    referral_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=referral_type,
        active=True
    )
    
    # 각 식당별 쿠폰 내용을 FINAL_EXAM_SPECIAL로 복사
    copied_count = 0
    for benefit in referral_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=final_exam_type,
            restaurant_id=benefit.restaurant_id,
            defaults={
                "title": benefit.title,
                "subtitle": benefit.subtitle,
                "benefit_json": benefit.benefit_json,
                "active": benefit.active,
            },
        )
        copied_count += 1


def remove_final_exam_benefits(apps, schema_editor):
    """FINAL_EXAM_SPECIAL의 식당별 쿠폰 내용을 삭제합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    try:
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
    except CouponType.DoesNotExist:
        return
    
    RestaurantCouponBenefit.objects.filter(coupon_type=final_exam_type).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0014_add_final_exam_event"),
    ]

    operations = [
        migrations.RunPython(copy_referral_benefits_to_final_exam, remove_final_exam_benefits),
    ]

