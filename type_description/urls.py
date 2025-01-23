from django.urls import path
from .views import get_type_descriptions, get_all_type_descriptions

urlpatterns = [
    path('type-descriptions/<str:type_code>/', get_type_descriptions, name='get_type_descriptions'),
    path('type-descriptions/all/<str:type_code>/', get_all_type_descriptions, name='get_all_type_descriptions'),
]
