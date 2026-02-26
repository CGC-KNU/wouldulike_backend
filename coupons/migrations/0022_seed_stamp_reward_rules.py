from django.db import migrations


def seed_stamp_reward_rules(apps, schema_editor):
    """기존 제휴 식당에 기본 스탬프 규칙(5, 10) 추가."""
    db_alias = schema_editor.connection.alias
    StampRewardRule = apps.get_model("coupons", "StampRewardRule")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT restaurant_id FROM restaurants_affiliate WHERE is_affiliate = TRUE"
        )
        restaurant_ids = [row[0] for row in cursor.fetchall()]

    default_config = {
        "thresholds": [
            {"stamps": 5, "coupon_type_code": "STAMP_REWARD_5"},
            {"stamps": 10, "coupon_type_code": "STAMP_REWARD_10"},
        ],
        "cycle_target": 10,
    }

    for rid in restaurant_ids:
        StampRewardRule.objects.using(db_alias).get_or_create(
            restaurant_id=rid,
            defaults={
                "rule_type": "THRESHOLD",
                "config_json": default_config,
                "active": True,
            },
        )


def reverse_seed(apps, schema_editor):
    """마이그레이션 롤백 시 시드된 규칙 삭제."""
    db_alias = schema_editor.connection.alias
    StampRewardRule = apps.get_model("coupons", "StampRewardRule")
    StampRewardRule.objects.using(db_alias).all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0021_add_stamp_reward_rule"),
    ]

    operations = [
        migrations.RunPython(seed_stamp_reward_rules, reverse_seed),
    ]
