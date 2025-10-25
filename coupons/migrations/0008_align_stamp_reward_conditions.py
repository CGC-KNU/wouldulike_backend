from django.db import migrations


def align_stamp_reward_conditions(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    base_codes = ["STAMP_REWARD_10", "STAMP_REWARD"]
    base_coupon = None
    for code in base_codes:
        try:
            base_coupon = CouponType.objects.get(code=code)
            break
        except CouponType.DoesNotExist:
            continue

    if base_coupon is None:
        return

    fields_to_copy = ["title", "benefit_json", "valid_days", "per_user_limit"]
    target_codes = ["STAMP_REWARD_5", "STAMP_REWARD_10"]

    for target_code in target_codes:
        target_coupon, created = CouponType.objects.get_or_create(
            code=target_code,
            defaults={field: getattr(base_coupon, field) for field in fields_to_copy},
        )
        updates = []
        for field in fields_to_copy:
            base_value = getattr(base_coupon, field)
            if getattr(target_coupon, field) != base_value:
                setattr(target_coupon, field, base_value)
                updates.append(field)
        if updates:
            target_coupon.save(update_fields=updates)

    benefits = RestaurantCouponBenefit.objects.filter(coupon_type=base_coupon)
    if not benefits.exists():
        return

    for benefit in benefits:
        for target_code in target_codes:
            target_coupon = CouponType.objects.get(code=target_code)
            RestaurantCouponBenefit.objects.update_or_create(
                coupon_type=target_coupon,
                restaurant_id=benefit.restaurant_id,
                defaults={
                    "title": benefit.title,
                    "subtitle": benefit.subtitle,
                    "benefit_json": benefit.benefit_json,
                    "active": benefit.active,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0007_add_stamp_reward_coupon_types"),
    ]

    operations = [
        migrations.RunPython(align_stamp_reward_conditions, migrations.RunPython.noop),
    ]
