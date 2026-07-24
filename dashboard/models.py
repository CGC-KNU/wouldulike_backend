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


class AdminAccount(models.Model):
    """추가 관리자 계정 (최대 MAX_ACCOUNTS명). 환경변수 슈퍼어드민과 별개로 로그인 가능."""
    MAX_ACCOUNTS = 8

    username = models.CharField(max_length=64, unique=True)
    password_hash = models.TextField()
    is_active = models.BooleanField(default=True, help_text="비활성화 시 로그인 불가")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dashboard_admin_account"

    def __str__(self):
        return f"AdminAccount:{self.username}"


# ─── 식당 캠페인 ───────────────────────────────────────────────────────────────

class RestaurantCampaignApplication(models.Model):
    """식당 측에서 신청한 주간 캠페인. 승인되면 해당 주 앱 접속 사용자에게 쿠폰 발급."""

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"          # 반려 — 슬롯 반환, 타 식당 신청 가능
    STATUS_REJECTED_HOLD = "REJECTED_HOLD"  # 반려 — 슬롯 보유, 해당 식당 우선 재신청
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "신청 대기"),
        (STATUS_APPROVED, "승인"),
        (STATUS_REJECTED, "반려"),
        (STATUS_REJECTED_HOLD, "반려(슬롯 보유)"),
        (STATUS_CANCELLED, "취소"),
    ]

    BENEFIT_PERCENT = "PERCENT"
    BENEFIT_FIXED = "FIXED"
    BENEFIT_FREE = "FREE"
    BENEFIT_OTHER = "OTHER"
    BENEFIT_TYPE_CHOICES = [
        (BENEFIT_PERCENT, "할인율(%)"),
        (BENEFIT_FIXED, "할인금액(원)"),
        (BENEFIT_FREE, "무료 제공"),
        (BENEFIT_OTHER, "기타"),
    ]

    restaurant_id = models.IntegerField(db_index=True)
    restaurant_name = models.CharField(max_length=255)
    week_start = models.DateField(db_index=True)  # 해당 주 월요일 (KST)

    # 쿠폰·캠페인 내용 (점주 입력)
    coupon_title = models.CharField(max_length=120)          # 쿠폰 제목 (앱 표시)
    coupon_subtitle = models.CharField(max_length=255, blank=True, default="")  # 쿠폰 부제
    coupon_notes = models.TextField(blank=True, default="")  # 쿠폰 이용 조건/비고
    benefit_type = models.CharField(max_length=10, choices=BENEFIT_TYPE_CHOICES, default=BENEFIT_OTHER)
    benefit_value = models.IntegerField(null=True, blank=True)  # 할인액(원) or 비율(%)
    campaign_description = models.TextField(blank=True, default="")  # 캠페인 소개 (관리자·앱 노출)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_notes = models.TextField(blank=True, default="")  # 관리자 메모/반려 사유

    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="campaign_applications",
        db_constraint=False,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reviewed_campaign_applications",
        db_constraint=False,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_restaurant_campaign_application"
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant_id", "week_start"],
                name="uq_campaign_restaurant_week",
            )
        ]
        ordering = ["-week_start", "-created_at"]

    def benefit_label(self) -> str:
        if self.benefit_type == self.BENEFIT_PERCENT and self.benefit_value:
            return f"{self.benefit_value}% 할인"
        if self.benefit_type == self.BENEFIT_FIXED and self.benefit_value:
            return f"{self.benefit_value:,}원 할인"
        if self.benefit_type == self.BENEFIT_FREE:
            return "무료 제공"
        return self.coupon_subtitle or "혜택"

    def __str__(self):
        return f"Campaign:{self.restaurant_name}({self.week_start})/{self.status}"


class RestaurantCampaignWeekConfig(models.Model):
    """주간 캠페인 최대 슬롯 수. week_start=None → 전역 기본값."""

    week_start = models.DateField(unique=True, null=True, blank=True)
    max_slots = models.IntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_campaign_week_config"

    def __str__(self):
        if self.week_start:
            return f"WeekConfig:{self.week_start}→max={self.max_slots}"
        return f"WeekConfig:default→max={self.max_slots}"

    @classmethod
    def get_max_slots(cls, week_start) -> int:
        """해당 주 설정이 없으면 전역 기본값 사용."""
        specific = cls.objects.filter(week_start=week_start).first()
        if specific:
            return specific.max_slots
        default = cls.objects.filter(week_start__isnull=True).first()
        return default.max_slots if default else 5


class RestaurantPlanCampaignLimit(models.Model):
    """플랜별 월간 캠페인 신청 가능 횟수 (0 = 제한 없음)."""

    plan_name = models.CharField(max_length=20, unique=True)  # FREE, BOOST, CONTENT
    max_per_month = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dashboard_plan_campaign_limit"

    def __str__(self):
        return f"PlanLimit:{self.plan_name}→{self.max_per_month}/월"
