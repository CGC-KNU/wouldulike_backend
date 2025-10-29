from django.db import migrations, models


def apply_coupon_type_policy(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")

    # All coupon types now rely on a unified global expiry date.
    CouponType.objects.update(valid_days=0)

    referral_codes = ["REFERRAL_BONUS_REFERRER", "REFERRAL_BONUS_REFEREE"]
    CouponType.objects.filter(code__in=referral_codes).update(per_user_limit=5)

    for coupon_type in CouponType.objects.exclude(benefit_json={}):
        if coupon_type.benefit_json:
            coupon_type.benefit_json = {}
            coupon_type.save(update_fields=["benefit_json"])


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0008_align_stamp_reward_conditions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coupontype",
            name="valid_days",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(apply_coupon_type_policy, migrations.RunPython.noop),
    ]
