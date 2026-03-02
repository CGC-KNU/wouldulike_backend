from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    KakaoLoginView,
    AppleLoginView,
    LogoutView,
    UnlinkView,
    DevLoginView,
    CustomTokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('kakao', KakaoLoginView.as_view(), name='kakao-login'),
    path('apple/login/', AppleLoginView.as_view(), name='apple-login'),
    path('refresh', CustomTokenRefreshView.as_view(), name='token-refresh'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token-refresh-alt'),  # 프론트엔드 요구사항
    path('verify', TokenVerifyView.as_view(), name='token-verify'),  # 토큰 검증 API
    path('logout', LogoutView.as_view(), name='logout'),
    path('unlink', UnlinkView.as_view(), name='unlink'),
    # Dev login endpoint (for local/testing)
    path('dev-login', DevLoginView.as_view(), name='dev-login'),
]
