from django.db import migrations


def update_knulike_title(apps, schema_editor):
    """KNULIKE CouponType title을 [학생회 제휴 쿠폰 🤝]로, RestaurantCouponBenefit subtitle만 업데이트.
    title(식당별 실제 쿠폰 내용)은 NEW_SEMESTER_SPECIAL에서 복원하여 유지."""
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="KNULIKE").update(
        title="[학생회 제휴 쿠폰 🤝]"
    )
    # subtitle만 [학생회 제휴 쿠폰 🤝]로, title은 NEW_SEMESTER_SPECIAL에서 복원
    try:
        new_semester_type = CouponType.objects.get(code="NEW_SEMESTER_SPECIAL")
        knulike_type = CouponType.objects.get(code="KNULIKE")
    except CouponType.DoesNotExist:
        return
    new_semester_benefits = RestaurantCouponBenefit.objects.filter(
        coupon_type=new_semester_type, active=True
    ).values("restaurant_id", "sort_order", "title")
    for ns in new_semester_benefits:
        RestaurantCouponBenefit.objects.filter(
            coupon_type=knulike_type,
            restaurant_id=ns["restaurant_id"],
            sort_order=ns.get("sort_order", 0),
        ).update(title=ns["title"], subtitle="[학생회 제휴 쿠폰 🤝]")


def revert_knulike_title(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    CouponType.objects.filter(code="KNULIKE").update(title="[KNULIKE 쿠폰]")
    RestaurantCouponBenefit.objects.filter(
        coupon_type__code="KNULIKE"
    ).update(subtitle="[KNULIKE 쿠폰]")


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0031_add_knulike_event"),
    ]

    operations = [
        migrations.RunPython(update_knulike_title, revert_knulike_title),
    ]
