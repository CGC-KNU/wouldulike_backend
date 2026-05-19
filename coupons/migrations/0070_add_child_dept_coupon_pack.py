from datetime import datetime, timezone

from django.db import migrations

CHILD_DEPT_SUBTITLE = "[아동학부 쿠폰팩 🐣]"


def add_child_dept_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    start_at = datetime(2026, 4, 30, 15, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 5, 31, 14, 59, 59, tzinfo=timezone.utc)

    CouponType.objects.update_or_create(
        code="CHILD_DEPT_COUPON_PACK",
        defaults={
            "title": CHILD_DEPT_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )
    Campaign.objects.update_or_create(
        code="CHILD_DEPT_COUPON_PACK_202605",
        defaults={
            "name": "아동학부 쿠폰팩 2026-05",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {"tiers": {"JUNYOUNG": 1, "JEONGHWAN": 3, "YUNJI": 5}},
        },
    )

    try:
        child_type = CouponType.objects.get(code="CHILD_DEPT_COUPON_PACK")
    except CouponType.DoesNotExist:
        return

    target_ids = set()
    for row in AffiliateRestaurant.objects.filter(is_affiliate=True).values(
        "restaurant_id", "pub_option", "category"
    ):
        rid = row["restaurant_id"]
        cat = (row.get("category") or "").strip()
        pub = (row.get("pub_option") or "").strip()
        is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
        if cat == "주점" or is_pub:
            target_ids.add(rid)
    target_ids.discard(298)

    if not target_ids:
        return

    source_type = None
    for code in ("PUB_JUJEOM_EVENT", "GAEHWALIKE", "MIDTERM_EVENT_SPECIAL"):
        try:
            source_type = CouponType.objects.get(code=code)
            break
        except CouponType.DoesNotExist:
            continue
    if source_type is None:
        return

    for benefit in RestaurantCouponBenefit.objects.filter(
        coupon_type=source_type,
        restaurant_id__in=target_ids,
        active=True,
    ):
        if benefit.restaurant_id == 298:
            continue
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=child_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": CHILD_DEPT_SUBTITLE,
                "benefit_json": benefit.benefit_json,
                "notes": getattr(benefit, "notes", "") or "",
                "active": benefit.active,
            },
        )


def revert_child_dept_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    child_type = CouponType.objects.filter(code="CHILD_DEPT_COUPON_PACK").first()
    if child_type:
        RestaurantCouponBenefit.objects.filter(coupon_type=child_type).delete()
    Campaign.objects.filter(code="CHILD_DEPT_COUPON_PACK_202605").update(
        active=False,
        start_at=None,
        end_at=None,
    )
    CouponType.objects.filter(code="CHILD_DEPT_COUPON_PACK").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0069_jungdunbam_stamp_display_rewards"),
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.RunPython(add_child_dept_event, revert_child_dept_event),
    ]
