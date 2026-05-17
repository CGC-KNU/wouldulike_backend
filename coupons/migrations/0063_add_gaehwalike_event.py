from datetime import datetime, timezone

from django.db import migrations

GAEHWALIKE_SUBTITLE = "[성년의날 행사 🌹]"


def add_gaehwalike_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    # 2026-05-01 00:00:00 ~ 2026-05-31 23:59:59 (KST)
    # UTC: 2026-04-30 15:00:00 ~ 2026-05-31 14:59:59
    start_at = datetime(2026, 4, 30, 15, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 5, 31, 14, 59, 59, tzinfo=timezone.utc)

    CouponType.objects.update_or_create(
        code="GAEHWALIKE",
        defaults={
            "title": GAEHWALIKE_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    Campaign.objects.update_or_create(
        code="GAEHWALIKE_EVENT",
        defaults={
            "name": "성년의날 GAEHWALIKE 쿠폰",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {"trigger": "COUPON_CODE", "code": "GAEHWALIKE"},
        },
    )

    try:
        source_type = CouponType.objects.get(code="MIDTERM_EVENT_SPECIAL")
        gaehwalike_type = CouponType.objects.get(code="GAEHWALIKE")
    except CouponType.DoesNotExist:
        return

    source_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=source_type,
        active=True,
    )
    for benefit in source_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=gaehwalike_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": GAEHWALIKE_SUBTITLE,
                "benefit_json": benefit.benefit_json,
                "notes": getattr(benefit, "notes", "") or "",
                "active": benefit.active,
            },
        )


def revert_gaehwalike_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    gaehwalike_type = CouponType.objects.filter(code="GAEHWALIKE").first()
    if gaehwalike_type:
        RestaurantCouponBenefit.objects.filter(coupon_type=gaehwalike_type).delete()
    Campaign.objects.filter(code="GAEHWALIKE_EVENT").update(
        active=False,
        start_at=None,
        end_at=None,
    )
    CouponType.objects.filter(code="GAEHWALIKE").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0062_jungdunbam_hide_from_affiliate_list"),
    ]

    operations = [
        migrations.RunPython(add_gaehwalike_event, revert_gaehwalike_event),
    ]
