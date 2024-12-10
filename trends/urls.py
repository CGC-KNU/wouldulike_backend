from django.urls import path
from .views import TrendListView

urlpatterns = [
    path('api/trends/', TrendListView.as_view(), name='trend-list'),
]
