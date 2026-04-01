"""
FULL_AFFILIATE_SPECIAL은 식당당 1행이어야 한다.
0044에서 REFERRAL_BONUS_REFEREE를 그대로 여러 줄 복사하면서 동일 식당에 FULL이 N행 생긴 경우를 정리한다.
피추천인 등 다른 타입의 여러 행은 그대로 둔다.
"""

from django.db import migrations


def dedupe_full_affiliate(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    alias = schema_editor.connection.alias
    mgr = RestaurantCouponBenefit.objects.db_manager(alias)

    try:
        full_ct = CouponType.objects.db_manager(alias).get(code="FULL_AFFILIATE_SPECIAL")
    except CouponType.DoesNotExist:
        return

    qs = (
        mgr.filter(coupon_type=full_ct, active=True)
        .order_by("restaurant_id", "sort_order", "id")
        .only("id", "restaurant_id")
    )

    prev_rid = None
    ids_to_delete = []
    for b in qs:
        rid = b.restaurant_id
        if rid != prev_rid:
            prev_rid = rid
            continue
        ids_to_delete.append(b.id)

    if ids_to_delete:
        mgr.filter(id__in=ids_to_delete).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0044_sync_full_affiliate_benefits_for_affiliates"),
    ]

    operations = [
        migrations.RunPython(dedupe_full_affiliate, noop_reverse),
    ]
