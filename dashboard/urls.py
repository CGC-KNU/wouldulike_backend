from django.urls import path
from . import views

urlpatterns = [
    path("restaurants/", views.OwnerRestaurantListView.as_view()),
    path("admin/restaurants/<int:restaurant_id>/", views.AdminRestaurantView.as_view()),
    path("admin/banner-popup/", views.AdminBannerPopupView.as_view()),
    path("admin/banner-popup/s3-scan/", views.AdminBannerPopupS3ScanView.as_view()),
    path("admin/config-debug/", views.AdminConfigDebugView.as_view()),
    path("admin/trends/", views.AdminTrendView.as_view()),
    path("admin/trends/<int:pk>/", views.AdminTrendView.as_view()),
    path("admin/popup-campaigns/", views.AdminPopupCampaignView.as_view()),
    path("admin/popup-campaigns/<int:pk>/", views.AdminPopupCampaignView.as_view()),
    path("admin/password/", views.AdminPasswordView.as_view()),
    path("images/presign/", views.PresignedUploadView.as_view()),
    path("auth/verify-owner/", views.VerifyOwnerView.as_view()),
    path("auth/app-token/", views.AppTokenView.as_view()),
    path("auth/admin-login/", views.AdminLoginView.as_view()),
    path("stats/", views.DashboardStatsView.as_view()),
    path("restaurant/", views.RestaurantInfoView.as_view()),
    path("coupon-types/", views.CouponTypesView.as_view()),
    path("coupon-benefits/", views.RestaurantCouponBenefitsView.as_view()),
    path("coupon-benefits/<int:pk>/", views.RestaurantCouponBenefitsView.as_view()),
    path("stamp-rule/", views.StampRewardRuleView.as_view()),
    path("admin/notifications/", views.AdminNotificationsView.as_view()),
    path("admin/notifications/<int:pk>/", views.AdminNotificationsView.as_view()),
    path("admin/notifications/<int:pk>/send-now/", views.AdminNotificationSendNowView.as_view()),
    # 식당 알림 예약
    path("owner/notification-schedule/", views.OwnerNotificationScheduleView.as_view()),
    path("owner/notification-schedule/<int:pk>/", views.OwnerNotificationScheduleView.as_view()),
    path("admin/restaurant-notifications/", views.AdminRestaurantNotificationView.as_view()),
    path("admin/restaurant-notifications/<int:pk>/", views.AdminRestaurantNotificationView.as_view()),
]
