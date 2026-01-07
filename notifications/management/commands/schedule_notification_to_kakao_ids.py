from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from notifications.models import Notification


class Command(BaseCommand):
    help = "특정 카카오 ID(들)를 대상으로 하는 예약 알림(Notification)을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "kakao_ids",
            nargs="+",
            help="알림을 보낼 대상 카카오 ID 목록 (공백으로 구분)",
        )
        parser.add_argument(
            "--message",
            type=str,
            required=True,
            help="전송할 알림 메시지 내용",
        )
        parser.add_argument(
            "--schedule-minutes",
            type=int,
            required=True,
            help="지금으로부터 N분 뒤에 전송되도록 예약 (필수)",
        )

    def handle(self, *args, **options):
        raw_kakao_ids = options["kakao_ids"]
        message = options["message"]
        schedule_minutes = options["schedule_minutes"]

        if schedule_minutes <= 0:
            self.stderr.write(
                self.style.ERROR("--schedule-minutes 값은 1 이상이어야 합니다.")
            )
            return

        # 숫자 형식으로 변환
        kakao_ids = []
        for raw in raw_kakao_ids:
            try:
                kakao_ids.append(int(raw))
            except ValueError:
                raise CommandError(f"유효하지 않은 카카오 ID 값입니다: {raw}")

        scheduled_time = timezone.now() + timezone.timedelta(minutes=schedule_minutes)

        notification = Notification.objects.create(
            content=message,
            scheduled_time=scheduled_time,
            sent=False,
            target_kakao_ids=kakao_ids,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ 예약 알림 생성 완료 (ID: {notification.id}, "
                f"전송 시각: {scheduled_time}, "
                f"대상 카카오 ID 수: {len(kakao_ids)}개)"
            )
        )
        self.stdout.write(
            "실제 전송은 python manage.py send_scheduled_notifications "
            "명령어(또는 스케줄러)에 의해 처리됩니다."
        )


