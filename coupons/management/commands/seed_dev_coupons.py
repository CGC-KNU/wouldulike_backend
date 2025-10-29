from django.core.management.base import BaseCommand
from django.utils import timezone

from coupons.models import Campaign, CouponType, MerchantPin


class Command(BaseCommand):
    help = "Seed dev data for coupons/stamps/flash testing"

    def add_arguments(self, parser):
        parser.add_argument("--restaurant", type=int, default=1, help="Restaurant ID for PIN setup")
        parser.add_argument("--pin", type=str, default="1234", help="Static PIN secret")
        parser.add_argument(
            "--flash-quota",
            type=int,
            default=None,
            help="Set today's remaining flash quota to this value (optional)",
        )

    def handle(self, *args, **opts):
        # Ensure coupon types
        ct_welcome, _ = CouponType.objects.get_or_create(
            code="WELCOME_3000",
            defaults={
                "title": "Welcome 3000",
                "valid_days": 0,
            },
        )
        ct_flash, _ = CouponType.objects.get_or_create(
            code="FLASH_3000",
            defaults={
                "title": "Flash 3000",
                "valid_days": 0,
            },
        )
        ct_reward_5, _ = CouponType.objects.get_or_create(
            code="STAMP_REWARD_5",
            defaults={
                "title": "Stamp Reward 5",
                "valid_days": 0,
            },
        )
        ct_reward_10, _ = CouponType.objects.get_or_create(
            code="STAMP_REWARD_10",
            defaults={
                "title": "Stamp Reward 10",
                "valid_days": 0,
            },
        )

        # Ensure campaigns
        camp_signup, _ = Campaign.objects.get_or_create(
            code="SIGNUP_WELCOME",
            defaults={"name": "Signup Welcome", "type": "SIGNUP", "active": True},
        )
        camp_stamp, _ = Campaign.objects.get_or_create(
            code="STAMP_REWARD",
            defaults={"name": "Stamp Reward", "type": "REFERRAL", "active": True},
        )
        camp_flash, _ = Campaign.objects.get_or_create(
            code="FLASH_8PM",
            defaults={"name": "Flash 8PM", "type": "FLASH", "active": True},
        )

        # Optional: set today's flash quota in Redis
        if opts.get("flash_quota") is not None:
            try:
                from django_redis import get_redis_connection

                conn = get_redis_connection()
                key = f"quota:{camp_flash.id}:{timezone.now().date():%Y%m%d}"
                conn.set(key, int(opts["flash_quota"]))
                self.stdout.write(self.style.NOTICE(f"Set flash quota key {key} to {opts['flash_quota']}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Skipping flash quota set (redis unavailable?): {e}"))

        # Ensure merchant PIN
        rid = int(opts["restaurant"]) if opts.get("restaurant") is not None else 1
        pin = opts.get("pin") or "1234"
        mp, created = MerchantPin.objects.get_or_create(
            restaurant_id=rid, defaults={"algo": "STATIC", "secret": pin}
        )
        if not created:
            mp.algo = "STATIC"
            mp.secret = pin
            mp.save(update_fields=["algo", "secret"])

        self.stdout.write(self.style.SUCCESS("Dev coupon/stamp/flash seed completed."))
