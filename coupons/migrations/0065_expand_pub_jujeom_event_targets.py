"""
0064 가 주점(category)만 복사했을 수 있어, 술집·주점 합집합 benefit 을 idempotent 하게 보강.
"""
from django.db import migrations

PUB_JUJEOM_SUBTITLE = "[주점 이벤트 🍻]"


def _target_ids(AffiliateRestaurant):
    target = set()
    for row in AffiliateRestaurant.objects.filter(is_affiliate=True).values(
        "restaurant_id", "pub_option", "category"
    ):
        rid = row["restaurant_id"]
        cat = (row.get("category") or "").strip()
        pub = (row.get("pub_option") or "").strip()
        is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
        if cat == "주점" or is_pub:
            target.add(rid)
    return target


def expand_pub_jujeom_benefits(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    try:
        source_type = CouponType.objects.get(code="GAEHWALIKE")
        pub_type = CouponType.objects.get(code="PUB_JUJEOM_EVENT")
    except CouponType.DoesNotExist:
        return

    target_ids = _target_ids(AffiliateRestaurant)
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


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0064_add_pub_jujeom_event"),
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.RunPython(expand_pub_jujeom_benefits, noop),
    ]
