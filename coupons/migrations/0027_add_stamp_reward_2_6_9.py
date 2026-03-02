from django.db import migrations


def add_stamp_reward_2_6_9(apps, schema_editor):
    """STAMP_REWARD_2, STAMP_REWARD_6, STAMP_REWARD_9 쿠폰 타입 추가."""
    db_alias = schema_editor.connection.alias
    CouponType = apps.get_model("coupons", "CouponType")

    specs = [
        {"code": "STAMP_REWARD_2", "defaults": {"title": "Stamp Reward (2)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_REWARD_6", "defaults": {"title": "Stamp Reward (6)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_REWARD_9", "defaults": {"title": "Stamp Reward (9)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
    ]

    for spec in specs:
        CouponType.objects.using(db_alias).get_or_create(code=spec["code"], defaults=spec["defaults"])


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0026_restaurantcouponbenefit_sort_order"),
    ]

    operations = [
        migrations.RunPython(add_stamp_reward_2_6_9, migrations.RunPython.noop),
    ]
