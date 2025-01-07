from django.urls import path
from trends.views import TrendListView, TrendDetailView

urlpatterns = [
    path('trend_list/', TrendListView.as_view(), name='trend-list'), # 트렌드 리스트 조회
    path('trend_detail/<int:pk>/', TrendDetailView.as_view(), name='trend-detail'), # 트렌드 상세 조회
]
