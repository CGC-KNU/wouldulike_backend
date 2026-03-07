from django.db import migrations


def add_knulike_event(apps, schema_editor):
    """KNULIKE 쿠폰 타입 및 캠페인 생성. 개강 기념 쿠폰(NEW_SEMESTER_SPECIAL)과 동일한 조건으로 3개 발급."""
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    # KNULIKE 쿠폰 타입 생성 (개강 기념과 동일한 benefit_json)
    CouponType.objects.update_or_create(
        code="KNULIKE",
        defaults={
            "title": "[학생회 제휴 쿠폰 🤝]",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    # KNULIKE 이벤트 Campaign 생성
    Campaign.objects.update_or_create(
        code="KNULIKE_EVENT",
        defaults={
            "name": "KNULIKE 추천코드 이벤트",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
    )

    # NEW_SEMESTER_SPECIAL의 식당별 쿠폰 내용을 KNULIKE로 복사 (개강 기념과 동일)
    try:
        new_semester_type = CouponType.objects.get(code="NEW_SEMESTER_SPECIAL")
        knulike_type = CouponType.objects.get(code="KNULIKE")
    except CouponType.DoesNotExist:
        return

    new_semester_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=new_semester_type,
        active=True,
    )

    for benefit in new_semester_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=knulike_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,  # 식당별 실제 쿠폰 내용 유지
                "subtitle": "[학생회 제휴 쿠폰 🤝]",
                "benefit_json": benefit.benefit_json,
                "active": benefit.active,
            },
        )


def remove_knulike_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    knulike_type = CouponType.objects.filter(code="KNULIKE").first()
    if knulike_type:
        RestaurantCouponBenefit.objects.filter(coupon_type=knulike_type).delete()
    Campaign.objects.filter(code="KNULIKE_EVENT").delete()
    CouponType.objects.filter(code="KNULIKE").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0030_update_new_semester_coupon_title"),
    ]

    operations = [
        migrations.RunPython(add_knulike_event, remove_knulike_event),
    ]
