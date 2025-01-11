<<<<<<< HEAD
from restaurants.models import Restaurant

# 데이터 가져오기 테스트
restaurants = Restaurant.objects.using('redshift').all()[:10]
for restaurant in restaurants:
    print(restaurant)
=======
from django.test import TestCase

# Create your tests here.
>>>>>>> e298dbcddba9311027e3c04bcc0c5d062bd49cdd
