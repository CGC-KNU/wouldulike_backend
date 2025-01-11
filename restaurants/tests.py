from django.contrib import admin
from .models import Restaurant

# Register your models here.
admin.site.register(Restaurant)

# 데이터 가져오기 테스트
restaurants = Restaurant.objects.using('redshift').all()[:10]
for restaurant in restaurants:
    print(restaurant)
