from django.conf import settings
from django.db import models


class Notification(models.Model):
    # 중복 생성/발송 방지용 키 (예: "weekly_mon:2026-05-09", "coupon_expiry_d2:2026-05-12")
    # - NULL은 허용하되, 값이 있는 경우에는 유일해야 함
    dedupe_key = models.CharField(max_length=120, null=True, blank=True, unique=True)
    content = models.TextField()
    scheduled_time = models.DateTimeField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    # 예약 대상이 전체가 아닌 경우, 특정 카카오 ID 목록을 JSON 배열로 저장
    target_kakao_ids = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content


class RestaurantNotificationSchedule(models.Model):
    """식당 알림 예약 — 점주가 신청, 정오(12:00 KST) / 저녁(18:00 KST) 두 슬롯"""

    SLOT_NOON = "noon"
    SLOT_EVENING = "evening"
    SLOT_CHOICES = [
        (SLOT_NOON, "정오 (12:00)"),
        (SLOT_EVENING, "저녁 (18:00)"),
    ]

    restaurant_id = models.IntegerField(db_index=True)
    restaurant_name = models.CharField(max_length=255)
    date = models.DateField(db_index=True)
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES)
    content = models.TextField()
    # UTC 기준 발송 시각 (noon → 03:00 UTC, evening → 09:00 UTC)
    scheduled_datetime = models.DateTimeField(db_index=True)
    sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restaurant_notification_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications_restaurant_schedule"
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant_id", "date", "slot"],
                name="unique_restaurant_date_slot",
            )
        ]

    def __str__(self):
        return f"{self.restaurant_name} {self.date} {self.slot}"