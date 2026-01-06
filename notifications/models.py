from django.db import models


class Notification(models.Model):
    content = models.TextField()
    scheduled_time = models.DateTimeField()
    sent = models.BooleanField(default=False)
    # 예약 대상이 전체가 아닌 경우, 특정 카카오 ID 목록을 JSON 배열로 저장
    target_kakao_ids = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content