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
    valid_days = models.PositiveIntegerField(default=7)
    per_user_limit = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.code


class Coupon(models.Model):
    STATUS = (
        ("ISSUED", "ISSUED"),
        ("REDEEMED", "REDEEMED"),
        ("EXPIRED", "EXPIRED"),
        ("CANCELED", "CANCELED"),
    )
    code = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coupons")
    coupon_type = models.ForeignKey(CouponType, on_delete=models.PROTECT)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="ISSUED")
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    # TODO: replace with FK when restaurant model is ready
    restaurant_id = models.IntegerField(null=True, blank=True)
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invite_code"
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
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made"
    )
    referee = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_from"
    )
    code_used = models.CharField(max_length=16)
    status = models.CharField(max_length=12, choices=STATUS, default="PENDING")
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["referrer", "referee"], name="uq_ref_pair")
        ]
