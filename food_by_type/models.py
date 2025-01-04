from django.db import models

class FoodTasteType(models.Model):
    id = models.AutoField(primary_key=True)  # 기본 키
    type_code = models.CharField(max_length=50)  # 유형 코드
    food_category = models.CharField(max_length=100)  # 음식 카테고리

    class Meta:
        db_table = 'foodtaste_types'  # 데이터베이스 테이블 이름
        managed = False  # Django가 테이블을 관리하지 않도록 설정
