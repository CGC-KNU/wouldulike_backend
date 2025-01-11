from django.db import models
import uuid
import json

class Restaurant(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)

class GuestUser(models.Model):
    # 게스트 사용자 필드 정의
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # 고유 사용자 ID (자동 생성, 고유, 수정 불가)
    type_code = models.CharField(max_length=4, null=True, blank=True)  # 유형 코드 (영어 4자리, 비어있을 수 있음)
    favorite_restaurants = models.TextField(null=True, blank=True)  # 찜한 음식점 이름 (JSON 형식, 비어있을 수 있음)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # 객체를 문자열로 표현하는 방법 정의. 둘을 하나로 가져옴
        return f"{self.uuid} - {self.type_code}"

    def get_favorite_restaurants(self):
        #JSON 형태로 저장된 favorite_restaurants를 파싱하여 리스트로 반환
        if self.favorite_restaurants:
            return json.loads(self.favorite_restaurants)
        return []

    def set_favorite_restaurants(self, restaurants):
        # 리스트를 JSON 문자열로 변환하여 favorite_restaurants에 저장
        self.favorite_restaurants = json.dumps(restaurants)