from django.db import migrations


def add_extended_stamp_reward_coupon_types(apps, schema_editor):
    """THRESHOLD(1,3,7) 및 VISIT 패턴용 쿠폰 타입 추가."""
    db_alias = schema_editor.connection.alias
    CouponType = apps.get_model("coupons", "CouponType")

    specs = [
        {"code": "STAMP_REWARD_1", "defaults": {"title": "Stamp Reward (1)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_REWARD_3", "defaults": {"title": "Stamp Reward (3)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_REWARD_7", "defaults": {"title": "Stamp Reward (7)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_VISIT_1_4", "defaults": {"title": "Stamp Visit Reward (1-4)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_VISIT_5_9", "defaults": {"title": "Stamp Visit Reward (5-9)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
        {"code": "STAMP_VISIT_10", "defaults": {"title": "Stamp Visit Reward (10)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
    ]

    for spec in specs:
        CouponType.objects.using(db_alias).get_or_create(code=spec["code"], defaults=spec["defaults"])


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0022_seed_stamp_reward_rules"),
    ]

    operations = [
        migrations.RunPython(add_extended_stamp_reward_coupon_types, migrations.RunPython.noop),
    ]
