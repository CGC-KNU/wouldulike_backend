from django.urls import path
from .views import get_random_foods
from .views import get_unique_random_foods

urlpatterns = [
    path('random-foods/', get_random_foods, name='get_random_foods'),
    path('unique-random-foods/', get_unique_random_foods, name='get_unique_random_foods'),
]
