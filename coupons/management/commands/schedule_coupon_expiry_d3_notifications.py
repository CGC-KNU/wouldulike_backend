from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from coupons.models import Coupon
from notifications.models import Notification


KST = ZoneInfo("Asia/Seoul")


def _kst_day_range_to_utc(target_kst_date):
    """
    target_kst_date(날짜)의 [00:00, 24:00) KST 구간을 UTC datetime 범위로 변환.
    """
    start_kst = datetime.combine(target_kst_date, time.min).replace(tzinfo=KST)
    end_kst = start_kst + timedelta(days=1)
    return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)


class Command(BaseCommand):
    help = "쿠폰 만료 D-2 사용자에게 보낼 예약 알림(Notification)을 생성/갱신합니다. (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-hour-kst",
            type=int,
            default=12,
            help="알림을 예약할 KST 시각(시). 기본값: 12 (12:10 KST)",
        )
        parser.add_argument(
            "--send-minute-kst",
            type=int,
            default=10,
            help="알림을 예약할 KST 시각(분). 기본값: 10 (12:10 KST)",
        )
        parser.add_argument(
            "--message",
            type=str,
            default="[아직 안 쓴 쿠폰이 있어요!]\n2일 후 만료될 수 있어요 ⏰\n쿠폰함에서 혜택을 확인하고, 오늘 점심에 바로 써보는 건 어때요?",
            help="전송할 알림 메시지",
        )

    def handle(self, *args, **options):
        send_hour_kst = int(options["send_hour_kst"])
        send_minute_kst = int(options["send_minute_kst"])
        message = options["message"]

        now = timezone.now()
        now_kst = now.astimezone(KST)
        target_expiry_kst_date = (now_kst.date() + timedelta(days=2))

        start_utc, end_utc = _kst_day_range_to_utc(target_expiry_kst_date)

        # 만료일이 D-2(해당 KST 날짜)에 해당하는 ISSUED 쿠폰 보유 사용자
        kakao_ids = list(
            Coupon.objects.filter(
                status="ISSUED",
                expires_at__gte=start_utc,
                expires_at__lt=end_utc,
            )
            .exclude(user__kakao_id__isnull=True)
            .values_list("user__kakao_id", flat=True)
            .distinct()
        )

        if not kakao_ids:
            self.stdout.write("No target users for D-2 expiry notification.")
            return

        # 예약 시각 (KST 기준 send_hour_kst:send_minute_kst)
        scheduled_kst = datetime.combine(
            now_kst.date(),
            time(hour=send_hour_kst, minute=send_minute_kst),
        ).replace(tzinfo=KST)
        # 이미 그 시각이 지났으면 즉시 발송되도록 now로
        scheduled_time = (
            now if scheduled_kst <= now_kst else scheduled_kst.astimezone(timezone.utc)
        )

        dedupe_key = f"coupon_expiry_d2:{target_expiry_kst_date.isoformat()}"

        notification, created = Notification.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "content": message,
                "scheduled_time": scheduled_time,
                "sent": False,
                "target_kakao_ids": kakao_ids,
            },
        )

        if created:
            self.stdout.write(
                f"Created D-2 expiry notification id={notification.id} "
                f"(targets={len(kakao_ids)}, dedupe_key={dedupe_key})"
            )
            return

        if notification.sent:
            self.stdout.write(
                f"Skipped: D-2 expiry notification already sent "
                f"(id={notification.id}, dedupe_key={dedupe_key})"
            )
            return

        # 재실행 시 대상 누락을 막기 위해 대상자를 합집합으로 갱신
        existing_ids = notification.target_kakao_ids or []
        merged_ids = sorted(set(existing_ids) | set(kakao_ids))

        fields_to_update = []
        if notification.content != message:
            notification.content = message
            fields_to_update.append("content")
        if notification.scheduled_time != scheduled_time:
            notification.scheduled_time = scheduled_time
            fields_to_update.append("scheduled_time")
        if merged_ids != existing_ids:
            notification.target_kakao_ids = merged_ids
            fields_to_update.append("target_kakao_ids")

        if fields_to_update:
            notification.save(update_fields=fields_to_update)

        self.stdout.write(
            f"Updated D-2 expiry notification id={notification.id} "
            f"(targets={len(notification.target_kakao_ids or [])}, dedupe_key={dedupe_key})"
        )

