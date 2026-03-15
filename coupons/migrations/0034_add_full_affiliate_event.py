from django.db import migrations


def add_full_affiliate_event(apps, schema_editor):
    """제휴식당 21종 전체 발급용 쿠폰 타입 및 캠페인 생성."""
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    # 제휴식당 전체 발급 쿠폰 타입 생성
    CouponType.objects.update_or_create(
        code="FULL_AFFILIATE_SPECIAL",
        defaults={
            "title": "제휴식당 전체 쿠폰",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    # 제휴식당 전체 발급 이벤트 Campaign 생성
    Campaign.objects.update_or_create(
        code="FULL_AFFILIATE_EVENT",
        defaults={
            "name": "제휴식당 전체 발급 이벤트",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
    )

    # REFERRAL_BONUS_REFEREE의 식당별 쿠폰 내용을 FULL_AFFILIATE_SPECIAL로 복사
    try:
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
        full_affiliate_type = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
    except CouponType.DoesNotExist:
        return

    referral_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=referral_type,
        active=True,
    )

    for benefit in referral_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=full_affiliate_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": "제휴식당 전체 쿠폰",
                "benefit_json": benefit.benefit_json,
                "active": benefit.active,
            },
        )


def remove_full_affiliate_event(apps, schema_editor):
    """제휴식당 전체 발급 이벤트 제거."""
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    try:
        full_affiliate_type = CouponType.objects.get(code="FULL_AFFILIATE_SPECIAL")
        RestaurantCouponBenefit.objects.filter(coupon_type=full_affiliate_type).delete()
    except CouponType.DoesNotExist:
        pass

    Campaign.objects.filter(code="FULL_AFFILIATE_EVENT").delete()
    CouponType.objects.filter(code="FULL_AFFILIATE_SPECIAL").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0033_fix_knulike_benefit_titles"),
    ]

    operations = [
        migrations.RunPython(add_full_affiliate_event, remove_full_affiliate_event),
    ]
