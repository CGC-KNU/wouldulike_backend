# models.py
from django.db import models
import uuid

class GuestUser(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preferences = models.JSONField(null=True, blank=True)  # 사용자 선호도 저장 예시

    def __str__(self):
        return str(self.uuid)
