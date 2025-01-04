from django.urls import path
from .views import get_random_foods

urlpatterns = [
    path('random-foods/<str:user_uuid>/', get_random_foods, name='get_random_foods'),
]
