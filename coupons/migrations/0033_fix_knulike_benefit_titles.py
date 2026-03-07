from django.db import migrations


def fix_knulike_titles(apps, schema_editor):
    """KNULIKE RestaurantCouponBenefit의 title을 REFERRAL_BONUS_REFEREE에서 복원.
    subtitle은 [학생회 제휴 쿠폰 🤝]로 유지."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    try:
        referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
        knulike_type = CouponType.objects.get(code="KNULIKE")
    except CouponType.DoesNotExist:
        return

    referral_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=referral_type,
        active=True,
    ).values("restaurant_id", "sort_order", "title")

    for ref in referral_benefits:
        updated = RestaurantCouponBenefit.objects.filter(
            coupon_type=knulike_type,
            restaurant_id=ref["restaurant_id"],
            sort_order=ref.get("sort_order", 0),
        ).update(title=ref["title"], subtitle="[학생회 제휴 쿠폰 🤝]")
        if updated == 0:
            # KNULIKE에 해당 식당 benefit이 없을 수 있음 (제외 식당 등)
            pass


def noop_revert(apps, schema_editor):
    """이전 상태로 복원 불가 - 데이터 손실 방지를 위해 noop"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0032_update_knulike_coupon_title"),
    ]

    operations = [
        migrations.RunPython(fix_knulike_titles, noop_revert),
    ]
