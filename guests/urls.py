from django.urls import path
from . import views

urlpatterns = [
    path('retrieve/', views.retrieve_guest_user, name='retrieve_guest_user'), # 새 사용자 생성 및 검색
    # 유형 코드 업데이트 (트레일링 슬래시 유무 모두 허용)
    path('update/type_code/', views.update_guest_user_type_code, name='update_guest_user_type_code'),
    path('update/type_code', views.update_guest_user_type_code),
    path('update/favorite_restaurants/', views.update_guest_user_favorite_restaurants, name='update_guest_user_favorite_restaurants'), # 찜 음식점 업데이트
    path('update/fcm_token/', views.update_guest_user_fcm_token, name='update_guest_user_fcm_token'), # FCM 토큰 업데이트
]
