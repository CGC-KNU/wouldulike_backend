from django.db import models
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password as django_check_password


class OwnerProfile(models.Model):
    """점주 계정 — User(카카오/Apple)와 AffiliateRestaurant 연결"""

    TIER_CHOICES = (
        ("FREE", "Free"),
        ("BOOST", "Boost"),
        ("CONTENT", "Content"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owner_profile",
        db_constraint=False,
    )
    restaurant = models.ForeignKey(
        "restaurants.AffiliateRestaurant",
        on_delete=models.PROTECT,
        db_column="restaurant_id",
        to_field="restaurant_id",
        related_name="owner_profile",
        db_constraint=False,
    )
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default="FREE")
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_owner_profile"

    def __str__(self):
        return f"Owner:{self.user_id} → Restaurant:{self.restaurant_id} ({self.tier})"


class AdminConfig(models.Model):
    """관리자 설정 key-value store (비밀번호 해시 등)"""
    key = models.CharField(max_length=64, unique=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_admin_config"

    @classmethod
    def get(cls, key: str) -> "AdminConfig | None":
        return cls.objects.filter(key=key).first()

    @classmethod
    def set_password(cls, key: str, raw_password: str):
        cls.objects.update_or_create(key=key, defaults={"value": make_password(raw_password)})

    @classmethod
    def check_password(cls, key: str, raw_password: str) -> bool:
        obj = cls.get(key)
        if not obj:
            return False
        return django_check_password(raw_password, obj.value)

    def __str__(self):
        return f"AdminConfig:{self.key}"
