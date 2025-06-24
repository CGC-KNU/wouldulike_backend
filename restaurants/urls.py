from django.urls import path
from .views import get_random_restaurants, get_nearby_restaurants

urlpatterns = [
    path('get-random-restaurants/', get_random_restaurants, name='get_random_restaurants'),
    path('get-nearby-restaurants/', get_nearby_restaurants, name='get_nearby_restaurants'),
]
