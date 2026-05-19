from datetime import datetime, timezone

from django.db import migrations

PUB_JUJEOM_SUBTITLE = "[주점 이벤트 🍻]"
AFFILIATE_CATEGORY_JUJEOM = "주점"


def _pub_jujeom_target_restaurant_ids(connection):
    """수요일 술집 기준 + category='주점' 제휴 식당 합집합 (raw SQL — migration state 모델에 필드 없음)."""
    if connection.vendor == "sqlite":
        return set()
    target = set()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT restaurant_id, category, pub_option
            FROM restaurants_affiliate
            WHERE is_affiliate = TRUE
            """
        )
        for rid, cat, pub in cursor.fetchall():
            cat = (cat or "").strip()
            pub = (pub or "").strip()
            is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
            if cat == AFFILIATE_CATEGORY_JUJEOM or is_pub:
                target.add(int(rid))
    return target


def add_pub_jujeom_event(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        return

    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    # 2026-05-01 00:00:00 ~ 2026-05-31 23:59:59 (KST)
    start_at = datetime(2026, 4, 30, 15, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 5, 31, 14, 59, 59, tzinfo=timezone.utc)

    CouponType.objects.update_or_create(
        code="PUB_JUJEOM_EVENT",
        defaults={
            "title": PUB_JUJEOM_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    Campaign.objects.update_or_create(
        code="PUB_JUJEOM_EVENT_CODES",
        defaults={
            "name": "주점 이벤트 쿠폰 (JUNYOUNG/JEONGHWAN/YUNJI)",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {
                "trigger": "COUPON_CODE",
                "codes": {
                    "JUNYOUNG": 1,
                    "JEONGHWAN": 3,
                    "YUNJI": 5,
                },
            },
        },
    )

    try:
        source_type = CouponType.objects.get(code="GAEHWALIKE")
        pub_type = CouponType.objects.get(code="PUB_JUJEOM_EVENT")
    except CouponType.DoesNotExist:
        return

    target_ids = _pub_jujeom_target_restaurant_ids(schema_editor.connection)
    if not target_ids:
        return

    source_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=source_type,
        restaurant_id__in=target_ids,
        active=True,
    )
    for benefit in source_benefits:
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=pub_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": PUB_JUJEOM_SUBTITLE,
                "benefit_json": benefit.benefit_json,
                "notes": getattr(benefit, "notes", "") or "",
                "active": benefit.active,
            },
        )


def revert_pub_jujeom_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    pub_type = CouponType.objects.filter(code="PUB_JUJEOM_EVENT").first()
    if pub_type:
        RestaurantCouponBenefit.objects.filter(coupon_type=pub_type).delete()
    Campaign.objects.filter(code="PUB_JUJEOM_EVENT_CODES").update(
        active=False,
        start_at=None,
        end_at=None,
    )
    CouponType.objects.filter(code="PUB_JUJEOM_EVENT").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0063_add_gaehwalike_event"),
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.RunPython(add_pub_jujeom_event, revert_pub_jujeom_event),
    ]
