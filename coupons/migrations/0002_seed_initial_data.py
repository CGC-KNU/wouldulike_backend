from django.db import migrations
from django.utils import timezone


def seed_initial_forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")

    # Coupon Types
    ct_data = [
        {
            "code": "WELCOME_3000",
            "title": "Welcome 3000",
            "benefit_json": {"type": "fixed", "value": 3000},
            "valid_days": 7,
        },
        {
            "code": "REFERRAL_BONUS_REFERRER",
            "title": "Referral Bonus (Referrer) 3000",
            "benefit_json": {"type": "fixed", "value": 3000},
            "valid_days": 14,
        },
        {
            "code": "REFERRAL_BONUS_REFEREE",
            "title": "Referral Bonus (Referee) 3000",
            "benefit_json": {"type": "fixed", "value": 3000},
            "valid_days": 14,
        },
        {
            "code": "FLASH_3000",
            "title": "Flash 3000",
            "benefit_json": {"type": "fixed", "value": 3000},
            "valid_days": 3,
        },
    ]

    for data in ct_data:
        CouponType.objects.update_or_create(
            code=data["code"], defaults={k: v for k, v in data.items() if k != "code"}
        )

    # Campaigns
    camp_data = [
        {
            "code": "SIGNUP_WELCOME",
            "name": "Signup Welcome",
            "type": "SIGNUP",
            "active": True,
            "rules_json": {},
        },
        {
            "code": "REFERRAL",
            "name": "Referral Program",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
        {
            "code": "FLASH_8PM",
            "name": "Flash Drop 8PM",
            "type": "FLASH",
            "active": True,
            "rules_json": {"quota_daily": 500},
        },
    ]

    now = timezone.now()
    for data in camp_data:
        Campaign.objects.update_or_create(
            code=data["code"],
            defaults={
                "name": data["name"],
                "type": data["type"],
                "active": data["active"],
                "rules_json": data["rules_json"],
                "start_at": data.get("start_at"),
                "end_at": data.get("end_at"),
            },
        )


def seed_initial_reverse(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")

    for code in ["SIGNUP_WELCOME", "REFERRAL", "FLASH_8PM"]:
        Campaign.objects.filter(code=code).delete()
    for code in [
        "WELCOME_3000",
        "REFERRAL_BONUS_REFERRER",
        "REFERRAL_BONUS_REFEREE",
        "FLASH_3000",
    ]:
        CouponType.objects.filter(code=code).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_forward, seed_initial_reverse),
    ]

