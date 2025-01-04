from django.urls import path
from .views import get_type_descriptions

urlpatterns = [
    path('type-descriptions/<str:type_code>/', get_type_descriptions, name='get_type_descriptions'),
]
