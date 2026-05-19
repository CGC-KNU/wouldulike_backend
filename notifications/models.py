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