from django.core.management.base import BaseCommand

from coupons.models import Campaign, CouponType


class Command(BaseCommand):
    help = "Seed initial Campaign and CouponType entries"

    def handle(self, *args, **kwargs):
        Campaign.objects.get_or_create(
            code="SIGNUP_WELCOME",
            defaults={"name": "Signup Welcome", "type": "SIGNUP"},
        )
        Campaign.objects.get_or_create(
            code="REFERRAL",
            defaults={"name": "Referral", "type": "REFERRAL"},
        )
        Campaign.objects.get_or_create(
            code="FLASH_8PM",
            defaults={
                "name": "8PM Flash",
                "type": "FLASH",
                "rules_json": {"quota_daily": 500},
            },
        )

        CouponType.objects.get_or_create(
            code="WELCOME_3000",
            defaults={
                "title": "Welcome ₩3,000",
                "benefit_json": {"type": "fixed", "value": 3000},
                "valid_days": 7,
                "per_user_limit": 1,
            },
        )
        CouponType.objects.get_or_create(
            code="REFERRAL_BONUS_REFERRER",
            defaults={
                "title": "Referral Bonus (Referrer)",
                "benefit_json": {"type": "fixed", "value": 2000},
                "valid_days": 14,
            },
        )
        CouponType.objects.get_or_create(
            code="REFERRAL_BONUS_REFEREE",
            defaults={
                "title": "Referral Bonus (New User)",
                "benefit_json": {"type": "fixed", "value": 2000},
                "valid_days": 14,
            },
        )

        CouponType.objects.get_or_create(
            code="FLASH_3000",
            defaults={
                "title": "Flash ₩3,000",
                "benefit_json": {"type": "fixed", "value": 3000},
                "valid_days": 3,
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded campaigns and coupon types"))
