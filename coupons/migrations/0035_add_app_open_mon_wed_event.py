"""
월/수 앱 접속 쿠폰용 CouponType, Campaign, RestaurantCouponBenefit 생성.

- APP_OPEN_MON: 월요일, 술집 아닌 식당 1장, valid_days=3
- APP_OPEN_WED: 수요일, 술집 1장, valid_days=3
- benefit은 REFERRAL_BONUS_REFEREE 기반으로 새로 생성 (기존과 분리)
"""
from django.db import migrations


def add_app_open_mon_wed_event(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign = apps.get_model("coupons", "Campaign")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    # CouponType 생성
    CouponType.objects.update_or_create(
        code="APP_OPEN_MON",
        defaults={
            "title": "월요일 앱 접속 쿠폰",
            "valid_days": 3,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )
    CouponType.objects.update_or_create(
        code="APP_OPEN_WED",
        defaults={
            "title": "수요일 앱 접속 쿠폰",
            "valid_days": 3,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    # Campaign 생성 (start_at/end_at 없음 = 무기한, 중지 시 active=False로 변경)
    Campaign.objects.update_or_create(
        code="APP_OPEN_MON_EVENT",
        defaults={
            "name": "월요일 앱 접속 쿠폰",
            "type": "FLASH",
            "active": True,
            "rules_json": {},
        },
    )
    Campaign.objects.update_or_create(
        code="APP_OPEN_WED_EVENT",
        defaults={
            "name": "수요일 앱 접속 쿠폰",
            "type": "FLASH",
            "active": True,
            "rules_json": {},
        },
    )

    # RestaurantCouponBenefit: REFERRAL_BONUS_REFEREE 기반으로 새 benefit 생성
    try:
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
        mon_type = CouponType.objects.get(code="APP_OPEN_MON")
        wed_type = CouponType.objects.get(code="APP_OPEN_WED")
    except CouponType.DoesNotExist:
        return

    for ct, subtitle in [(mon_type, "월요일 앱 접속 쿠폰"), (wed_type, "수요일 앱 접속 쿠폰")]:
        referral_benefits = RestaurantCouponBenefit.objects.filter(
            coupon_type=referral_type,
            active=True,
        )
        for benefit in referral_benefits:
            RestaurantCouponBenefit.objects.update_or_create(
                coupon_type=ct,
                restaurant_id=benefit.restaurant_id,
                sort_order=getattr(benefit, "sort_order", 0),
                defaults={
                    "title": benefit.title,
                    "subtitle": subtitle,
                    "benefit_json": benefit.benefit_json,
                    "active": True,
                },
            )


def remove_app_open_mon_wed_event(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign = apps.get_model("coupons", "Campaign")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    for code in ("APP_OPEN_MON", "APP_OPEN_WED"):
        try:
            ct = CouponType.objects.get(code=code)
            RestaurantCouponBenefit.objects.filter(coupon_type=ct).delete()
        except CouponType.DoesNotExist:
            pass

    Campaign.objects.filter(code__in=("APP_OPEN_MON_EVENT", "APP_OPEN_WED_EVENT")).delete()
    CouponType.objects.filter(code__in=("APP_OPEN_MON", "APP_OPEN_WED")).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0034_add_full_affiliate_event"),
    ]

    operations = [
        migrations.RunPython(add_app_open_mon_wed_event, remove_app_open_mon_wed_event),
    ]
