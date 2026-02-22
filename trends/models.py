from django.db import models

class Trend(models.Model):
    title = models.CharField(max_length=255)  # 간단한 제목
    description = models.TextField()  # 간단한 설명
    image = models.ImageField(upload_to='trend_images/')  # 사진
    blog_link = models.URLField()  # 블로그 링크
    created_at = models.DateTimeField(auto_now_add=True)  # 생성 날짜
    updated_at = models.DateTimeField(auto_now=True)  # 업데이트 날짜

    def __str__(self):
        return self.title


class PopupCampaign(models.Model):
    title = models.CharField(max_length=120)
    image_url = models.URLField(max_length=500)
    instagram_url = models.URLField(max_length=500)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "popup_campaigns"
        ordering = ("display_order", "-created_at")
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_at__gt=models.F("start_at")),
                name="popup_campaigns_end_at_after_start_at",
            ),
        ]

    def __str__(self):
        return self.title
