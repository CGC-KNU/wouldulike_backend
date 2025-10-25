from django.db import migrations


def add_stamp_reward_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")

    campaign_defaults = {
        "name": "Stamp Reward",
        "type": "REFERRAL",
        "active": True,
        "rules_json": {},
    }
    campaign, created = Campaign.objects.get_or_create(
        code="STAMP_REWARD",
        defaults=campaign_defaults,
    )
    if not created:
        updates = {}
        if not campaign.name:
            updates["name"] = campaign_defaults["name"]
        if not campaign.active:
            updates["active"] = True
        if updates:
            for field, value in updates.items():
                setattr(campaign, field, value)
            campaign.save(update_fields=list(updates.keys()))

    coupon_type_specs = [
        {
            "code": "STAMP_REWARD_5",
            "defaults": {
                "title": "Stamp Reward (5)",
                "benefit_json": {"type": "fixed", "value": 3000},
                "valid_days": 14,
                "per_user_limit": 999,
            },
        },
        {
            "code": "STAMP_REWARD_10",
            "defaults": {
                "title": "Stamp Reward (10)",
                "benefit_json": {"type": "fixed", "value": 3000},
                "valid_days": 14,
                "per_user_limit": 999,
            },
        },
    ]

    for spec in coupon_type_specs:
        ct, created = CouponType.objects.get_or_create(
            code=spec["code"],
            defaults=spec["defaults"],
        )
        if not created:
            updates = []
            for field, value in spec["defaults"].items():
                if getattr(ct, field) != value:
                    setattr(ct, field, value)
                    updates.append(field)
            if updates:
                ct.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0006_restaurant_coupon_benefits"),
    ]

    operations = [
        migrations.RunPython(add_stamp_reward_coupon_types, migrations.RunPython.noop),
    ]
