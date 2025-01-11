from django.db import models

class Restaurant(models.Model):
<<<<<<< HEAD
    id = models.IntegerField(primary_key=True)
=======
>>>>>>> e298dbcddba9311027e3c04bcc0c5d062bd49cdd
    name = models.CharField(max_length=255)  # 음식점 이름
    status = models.CharField(max_length=50)  # 상태
    address_zip_code = models.CharField(max_length=50, null=True, blank=True)  # 우편번호
    road_zip_code = models.CharField(max_length=25, null=True, blank=True)  # 도로명 우편번호
    road_full_address = models.CharField(max_length=500, null=True, blank=True)  # 도로명 전체 주소
    road_address = models.CharField(max_length=500, null=True, blank=True)  # 도로명 주소
    x = models.FloatField(null=True, blank=True)  # x좌표
    y = models.FloatField(null=True, blank=True)  # y좌표
    phone_number = models.CharField(max_length=50, null=True, blank=True)  # 전화번호
    category_1 = models.CharField(max_length=50, null=True, blank=True)  # 카테고리 1
    category_2 = models.CharField(max_length=50, null=True, blank=True)  # 카테고리 2
    district_name = models.CharField(max_length=50, null=True, blank=True)  # 구/군 이름
    attribute_1 = models.CharField(max_length=5, null=True, blank=True)  # 속성 1
    attribute_2 = models.CharField(max_length=5, null=True, blank=True)  # 속성 2
    attribute_3 = models.CharField(max_length=5, null=True, blank=True)  # 속성 3
    attribute_4 = models.CharField(max_length=5, null=True, blank=True)  # 속성 4

<<<<<<< HEAD
    def __str__(self):
        return self.name

    class Meta:
        db_table = 'restaurant_new'  # 데이터베이스 테이블 이름
=======
    class Meta:
        db_table = 'food_attribute'  # 데이터베이스 테이블 이름
>>>>>>> e298dbcddba9311027e3c04bcc0c5d062bd49cdd
        managed = False  # Django가 테이블을 관리하지 않도록 설정
