from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.core.management import call_command

from .models import Notification
from .serializers import NotificationSerializer

KST = ZoneInfo("Asia/Seoul")


class NotificationListView(APIView):
    def get(self, request):
        notifications = Notification.objects.filter(
            scheduled_time__gte=timezone.now()
        ).order_by("scheduled_time")
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def _is_valid_cron_token(request) -> bool:
    expected_token = getattr(settings, "CRON_SECRET_TOKEN", None)
    received_token = request.headers.get("X-CRON-TOKEN")
    return bool(expected_token and received_token == expected_token)


def _is_weekly_allowed_window(day_key: str) -> bool:
    """
    허용 시간: KST 기준 월/수 11:50~11:59.
    """
    now_kst = timezone.now().astimezone(KST)
    expected_weekday = {"mon": 0, "wed": 2}.get(day_key)
    if expected_weekday is None:
        return False
    if now_kst.weekday() != expected_weekday:
        return False
    return now_kst.hour == 11 and 50 <= now_kst.minute <= 59


@csrf_exempt
@require_http_methods(["GET", "POST"])
def trigger_send_scheduled_notifications(request):
    """
    내부용 스케줄 트리거 엔드포인트.

    - GCP Cloud Scheduler 등 외부 스케줄러가 이 URL을 주기적으로 호출
    - 헤더의 X-CRON-TOKEN 값이 settings.CRON_SECRET_TOKEN 과 일치해야 실행
    """
    # 간단한 토큰 기반 보호 (외부에서 임의 호출 방지)
    if not _is_valid_cron_token(request):
        return HttpResponseForbidden("Forbidden")

    # 예약된 알림 발송 커맨드 실행
    call_command("send_scheduled_notifications")

    return HttpResponse("OK")


def _trigger_weekly_notification(day_key: str):
    """
    매주 요일별 정기 알림 발송.
    - day_key: 'mon' | 'wed'
    - settings.WEEKLY_MON_MESSAGE, WEEKLY_WED_MESSAGE 에서 메시지 로드
    """
    message = getattr(
        settings,
        f"WEEKLY_{day_key.upper()}_MESSAGE",
        f"정기 알림 ({day_key})",
    )
    if not message:
        message = f"정기 알림 ({day_key})"

    now = timezone.now()
    duplicate_window_start = now - timedelta(minutes=15)
    recent_duplicate = (
        Notification.objects.filter(
            content=message,
            target_kakao_ids=None,
            created_at__gte=duplicate_window_start,
        )
        .order_by("-created_at")
        .first()
    )
    if recent_duplicate:
        return recent_duplicate

    notification = Notification.objects.create(
        content=message,
        scheduled_time=now,
        sent=False,
        target_kakao_ids=None,
    )
    call_command("send_scheduled_notifications", "--notification-id", str(notification.id))
    return notification


@csrf_exempt
@require_http_methods(["GET", "POST"])
def trigger_weekly_mon(request):
    """
    매주 월요일 11:50 KST에 Cloud Scheduler가 호출.
    X-CRON-TOKEN 헤더 필수.
    """
    if not _is_valid_cron_token(request):
        return HttpResponseForbidden("Forbidden")
    if not _is_weekly_allowed_window("mon"):
        return HttpResponse("SKIPPED")
    _trigger_weekly_notification("mon")
    return HttpResponse("OK")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def trigger_weekly_wed(request):
    """
    매주 수요일 11:50 KST에 Cloud Scheduler가 호출.
    X-CRON-TOKEN 헤더 필수.
    """
    if not _is_valid_cron_token(request):
        return HttpResponseForbidden("Forbidden")
    if not _is_weekly_allowed_window("wed"):
        return HttpResponse("SKIPPED")
    _trigger_weekly_notification("wed")
    return HttpResponse("OK")