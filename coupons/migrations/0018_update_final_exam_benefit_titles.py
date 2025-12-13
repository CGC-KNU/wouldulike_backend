from django.db import migrations


def update_final_exam_benefit_titles(apps, schema_editor):
    """FINAL_EXAM_SPECIAL 쿠폰 타입의 RestaurantCouponBenefit title을 '기말고사 쪽지 이벤트'로 업데이트합니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    try:
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
    except CouponType.DoesNotExist:
        return
    
    # FINAL_EXAM_SPECIAL 쿠폰 타입의 모든 RestaurantCouponBenefit의 title 업데이트
    updated_count = RestaurantCouponBenefit.objects.filter(
        coupon_type=final_exam_type
    ).update(title="기말고사 쪽지 이벤트")


def revert_final_exam_benefit_titles(apps, schema_editor):
    """FINAL_EXAM_SPECIAL 쿠폰 타입의 RestaurantCouponBenefit title을 원래대로 되돌립니다."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    
    try:
        final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
    except CouponType.DoesNotExist:
        return
    
    # REFERRAL_BONUS_REFEREE의 title로 복원 (식당별로 매칭)
    final_exam_benefits = RestaurantCouponBenefit.objects.filter(coupon_type=final_exam_type)
    referral_benefits = RestaurantCouponBenefit.objects.filter(coupon_type=referral_type)
    
    referral_title_map = {b.restaurant_id: b.title for b in referral_benefits}
    
    for benefit in final_exam_benefits:
        if benefit.restaurant_id in referral_title_map:
            benefit.title = referral_title_map[benefit.restaurant_id]
            benefit.save()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0017_configure_goni_and_gugupocha"),
    ]

    operations = [
        migrations.RunPython(update_final_exam_benefit_titles, revert_final_exam_benefit_titles),
    ]

