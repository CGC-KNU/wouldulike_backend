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
