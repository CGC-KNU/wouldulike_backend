from django.db import models
from django.contrib.postgres.fields import ArrayField


class AffiliateRestaurant(models.Model):
    """Read-only mapping of affiliate restaurants stored in CloudSQL."""

    restaurant_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    is_affiliate = models.BooleanField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    zone = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    url = models.CharField(max_length=500, null=True, blank=True)
    s3_image_urls = ArrayField(models.TextField(), null=True, blank=True, default=list)
    description = models.TextField(null=True, blank=True)
    main_menu = models.CharField(max_length=255, null=True, blank=True)
    naver_alarm_coupon_enabled = models.BooleanField(null=True, blank=True)
    naver_alarm_coupon_content = models.TextField(null=True, blank=True)
    people_counts = ArrayField(models.CharField(max_length=20), null=True, blank=True, default=list)
    meal_purpose = models.CharField(max_length=20, null=True, blank=True)
    pub_option = models.CharField(max_length=10, null=True, blank=True)
    soup_option = models.CharField(max_length=10, null=True, blank=True)
    spicy_option = models.CharField(max_length=10, null=True, blank=True)
    main_ingredients = ArrayField(models.CharField(max_length=20), null=True, blank=True, default=list)
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
