from django.urls import path
from .views import get_restaurants_by_foods

urlpatterns = [
    path('restaurants/<str:user_uuid>/', get_restaurants_by_foods, name='get_restaurants_by_foods'),
]
