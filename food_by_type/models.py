from django.db import models

# Food 테이블 모델
class Food(models.Model):
    food_id = models.AutoField(primary_key=True)  # 기본 키
    food_name = models.CharField(max_length=100)  # 음식 이름
    food_image_url = models.CharField(max_length=255, null=True)  # 음식 이미지 URL
    description = models.TextField(null=True)  # 음식 설명

    class Meta:
        db_table = 'foods'  # 테이블 이름
        managed = False  # Django가 이 테이블을 관리하지 않도록 설정

# TypeCode 테이블 모델
class TypeCode(models.Model):
    type_code_id = models.AutoField(primary_key=True)
    type_code = models.CharField(max_length=50)  # 유형 코드
    
    class Meta:
        db_table = 'type_codes'  # 테이블 이름
        managed = False  # Django가 이 테이블을 관리하지 않도록 설정

# TypeCodeFood 테이블 모델
class TypeCodeFood(models.Model):
    type_code_id = models.IntegerField()  # id 필드는 기본키와 함께 사용
    food_id = models.IntegerField()  # food_id 필드

    # 복합 기본 키 설정
    class Meta:
        db_table = 'type_code_foods'  # 테이블 이름
        managed = False  # Django가 이 테이블을 관리하지 않도록 설정
        unique_together = ('type_code_id', 'food_id')  # id와 food_id가 복합 기본 키로 작동하도록 설정
