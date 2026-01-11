from django.urls import path

from .views import NotificationListView, trigger_send_scheduled_notifications

urlpatterns = [
    # 예약된 알림 목록 조회 (기존 기능)
    path("list/", NotificationListView.as_view(), name="notification-list"),
    # 내부용 스케줄 트리거 (GCP Cloud Scheduler 등에서 호출)
    path(
        "internal/cron/send-scheduled-notifications/",
        trigger_send_scheduled_notifications,
        name="notifications-cron-trigger",
    ),
]