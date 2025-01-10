from django.urls import path
from .views import get_random_restaurants

urlpatterns = [
    path('get-random-restaurants/', get_random_restaurants, name='get_random_restaurants'),
]
