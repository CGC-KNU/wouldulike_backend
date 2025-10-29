from django.db import models
from django.conf import settings
from django.utils import timezone


class Campaign(models.Model):
    TYPE = (
        ("SIGNUP", "Signup"),
        ("REFERRAL", "Referral"),
        ("FLASH", "FlashDrop"),
    )
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=20, choices=TYPE)
    active = models.BooleanField(default=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    # Example: {"quota_daily": 500}
    rules_json = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.code}({self.type})"


class CouponType(models.Model):
    # ex) WELCOME_3000
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=80)
    # {"type":"fixed","value":3000} / {"type":"percent","value":20,"max":5000}
    benefit_json = models.JSONField(default=dict)
    valid_days = models.PositiveIntegerField(default=0)
    per_user_limit = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.code


class RestaurantCouponBenefit(models.Model):
    coupon_type = models.ForeignKey(
        CouponType,
        on_delete=models.CASCADE,
        related_name="restaurant_benefits",
    )
    restaurant = models.ForeignKey(
        "restaurants.AffiliateRestaurant",
        on_delete=models.CASCADE,
        db_column="restaurant_id",
        to_field="restaurant_id",
        related_name="coupon_benefits",
        db_constraint=False,
    )
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=255, blank=True, default="")
    benefit_json = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["coupon_type", "restaurant"], name="uq_coupon_type_restaurant"
            )
        ]

    def __str__(self):
        return f"{self.coupon_type.code} @ {self.restaurant_id}"


class Coupon(models.Model):
    STATUS = (
        ("ISSUED", "ISSUED"),
        ("REDEEMED", "REDEEMED"),
        ("EXPIRED", "EXPIRED"),
        ("CANCELED", "CANCELED"),
    )
    code = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupons",
        db_constraint=False,
    )
    coupon_type = models.ForeignKey(CouponType, on_delete=models.PROTECT)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="ISSUED")
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    # TODO: replace with FK when restaurant model is ready
    restaurant_id = models.IntegerField(null=True, blank=True)
    benefit_snapshot = models.JSONField(null=True, blank=True)
    # Duplicate issue guard key
    issue_key = models.CharField(max_length=120, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "coupon_type", "campaign", "issue_key"],
                name="uq_coupon_issue_guard",
            )
        ]

    def __str__(self):
        return f"{self.code}({self.status})"


class InviteCode(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invite_code", db_constraint=False
    )
    code = models.CharField(max_length=16, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Referral(models.Model):
    STATUS = (
        ("PENDING", "PENDING"),
        ("QUALIFIED", "QUALIFIED"),
        ("REJECTED", "REJECTED"),
    )
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made", db_constraint=False
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_from", db_constraint=False
    )
    code_used = models.CharField(max_length=16)
    status = models.CharField(max_length=12, choices=STATUS, default="PENDING")
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["referrer", "referee"], name="uq_ref_pair")
        ]


class MerchantPin(models.Model):
    restaurant = models.OneToOneField(
        "restaurants.AffiliateRestaurant",
        on_delete=models.CASCADE,
        db_column="restaurant_id",
        to_field="restaurant_id",
        related_name="merchant_pin",
        db_constraint=False,
        null=True,
        blank=True,
    )
    # STATIC | TOTP
    algo = models.CharField(max_length=10, default="STATIC")
    # STATIC 핀 or TOTP 시드
    secret = models.CharField(max_length=128)
    # TOTP 주기(초)
    period_sec = models.PositiveIntegerField(default=30)
    last_rotated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        name = getattr(self.restaurant, "name", None)
        base = f"PIN:{self.restaurant_id}({self.algo})"
        return f"PIN:{self.restaurant_id} {name}({self.algo})" if name else base


class StampWallet(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stamp_wallets", db_constraint=False
    )
    restaurant_id = models.IntegerField(db_index=True)
    # 현재 라운드 누적
    stamps = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "restaurant_id"], name="uq_stamp_wallet_user_restaurant"
            )
        ]

    def __str__(self):
        return f"Wallet:{self.user_id}:{self.restaurant_id}={self.stamps}"


class StampEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stamp_events", db_constraint=False
    )
    restaurant_id = models.IntegerField(db_index=True)
    # +1 적립, -1 정정
    delta = models.SmallIntegerField(default=+1)
    # PIN/QR/OTP 등
    source = models.CharField(max_length=10, default="PIN")
    created_at = models.DateTimeField(default=timezone.now)
    metadata_json = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"StampEvent u={self.user_id} r={self.restaurant_id} d={self.delta} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
