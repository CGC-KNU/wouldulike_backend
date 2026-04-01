from django.urls import include, path


urlpatterns = [
    # 쿠폰/추천코드 발급 로직 테스트에 필요한 URL만 포함
    path("", include("coupons.api.urls")),
]

