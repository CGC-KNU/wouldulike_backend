from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import KakaoLoginView, LogoutView, UnlinkView

urlpatterns = [
    path('kakao', KakaoLoginView.as_view(), name='kakao-login'),
    path('refresh', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('unlink', UnlinkView.as_view(), name='unlink'),
]