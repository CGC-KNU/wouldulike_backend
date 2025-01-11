from django.test import TestCase
from restaurants.models import Restaurant

class RestaurantTestCase(TestCase):
    databases = {'default', 'redshift'}  # Redshift 데이터베이스 허용

    def test_fetch_restaurants(self):
        try:
            # Redshift에서 데이터 가져오기
            restaurants = Restaurant.objects.using('redshift').all()[:10]
            self.assertGreater(len(restaurants), 0, "No restaurants fetched!")
            print("Fetched Restaurants:", restaurants)
        except Exception as e:
            self.fail(f"Fetching restaurants failed with error: {e}")
