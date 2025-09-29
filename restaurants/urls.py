from django.urls import path
from .views import (
    get_random_restaurants,
    get_nearby_restaurants,
    get_affiliate_restaurants,
    get_affiliate_restaurant_detail,
)

urlpatterns = [
    path('get-random-restaurants/', get_random_restaurants, name='get_random_restaurants'),
    path('get-nearby-restaurants/', get_nearby_restaurants, name='get_nearby_restaurants'),
    path('affiliate-restaurants/', get_affiliate_restaurants, name='get_affiliate_restaurants'),
    path('affiliate-restaurants/detail/', get_affiliate_restaurant_detail, name='get_affiliate_restaurant_detail'),
]
