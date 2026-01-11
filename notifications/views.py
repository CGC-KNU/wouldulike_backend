from django.conf import settings
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.core.management import call_command

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    def get(self, request):
        notifications = Notification.objects.filter(
            scheduled_time__gte=timezone.now()
        ).order_by("scheduled_time")
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


def trigger_send_scheduled_notifications(request):
    """
    내부용 스케줄 트리거 엔드포인트.

    - GCP Cloud Scheduler 등 외부 스케줄러가 이 URL을 주기적으로 호출
    - 헤더의 X-CRON-TOKEN 값이 settings.CRON_SECRET_TOKEN 과 일치해야 실행
    """
    # 간단한 토큰 기반 보호 (외부에서 임의 호출 방지)
    expected_token = getattr(settings, "CRON_SECRET_TOKEN", None)
    received_token = request.headers.get("X-CRON-TOKEN")

    if not expected_token or received_token != expected_token:
        return HttpResponseForbidden("Forbidden")

    # 예약된 알림 발송 커맨드 실행
    call_command("send_scheduled_notifications")

    return HttpResponse("OK")