from django.db import models


class AffiliateRestaurant(models.Model):
    """Read-only mapping of affiliate restaurants stored in CloudSQL."""

    restaurant_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    pin_secret = models.CharField(max_length=128, null=True, blank=True)
    pin_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "restaurants_affiliate"
        managed = False

    def __str__(self):
        return f"Affiliate:{self.restaurant_id} {self.name}"


class Restaurant(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    address_zip_code = models.CharField(max_length=50, null=True, blank=True)
    road_zip_code = models.CharField(max_length=25, null=True, blank=True)
    road_full_address = models.CharField(max_length=500, null=True, blank=True)
    road_address = models.CharField(max_length=500, null=True, blank=True)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    category_1 = models.CharField(max_length=50, null=True, blank=True)
    category_2 = models.CharField(max_length=50, null=True, blank=True)
    district_name = models.CharField(max_length=50, null=True, blank=True)
    attribute_1 = models.CharField(max_length=5, null=True, blank=True)
    attribute_2 = models.CharField(max_length=5, null=True, blank=True)
    attribute_3 = models.CharField(max_length=5, null=True, blank=True)
    attribute_4 = models.CharField(max_length=5, null=True, blank=True)
    liked_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'daegu_restaurants'  # 데이터베이스 테이블 이름
        managed = False  # Django가 테이블을 관리하지 않도록 설정
