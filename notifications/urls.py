from django.urls import path

from .views import (
    NotificationListView,
    trigger_send_scheduled_notifications,
    trigger_weekly_mon,
    trigger_weekly_wed,
    trigger_coupon_expiry_d3,
)

urlpatterns = [
    # 예약된 알림 목록 조회 (기존 기능)
    path("list/", NotificationListView.as_view(), name="notification-list"),
    # 내부용 스케줄 트리거 (GCP Cloud Scheduler 등에서 호출)
    path(
        "internal/cron/send-scheduled-notifications/",
        trigger_send_scheduled_notifications,
        name="notifications-cron-trigger",
    ),
    # 매주 월/수 정기 알림 (각각 다른 메시지)
    path(
        "internal/cron/weekly-mon/",
        trigger_weekly_mon,
        name="notifications-cron-weekly-mon",
    ),
    path(
        "internal/cron/weekly-wed/",
        trigger_weekly_wed,
        name="notifications-cron-weekly-wed",
    ),
    # 쿠폰 만료 D-3 알림 스케줄 적재 (매일 1회 호출 권장)
    path(
        "internal/cron/coupon-expiry-d3/",
        trigger_coupon_expiry_d3,
        name="notifications-cron-coupon-expiry-d3",
    ),
]