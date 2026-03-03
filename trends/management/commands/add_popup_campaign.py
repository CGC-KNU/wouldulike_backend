"""
팝업 캠페인 추가 management command.

사용 예:
  python manage.py add_popup_campaign \\
    --title "이벤트 팝업" \\
    --image-url "https://example.com/popup.png" \\
    --instagram-url "https://instagram.com/..." \\
    --start-at "2025-03-01 00:00" \\
    --end-at "2025-03-31 23:59"
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from trends.models import PopupCampaign


def parse_datetime(value: str):
    """YYYY-MM-DD 또는 YYYY-MM-DD HH:MM 형식 파싱. UTC로 저장."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return timezone.make_aware(dt, timezone.utc)
        except ValueError:
            continue
    raise CommandError(
        f"날짜 형식 오류: '{value}'. "
        "YYYY-MM-DD 또는 YYYY-MM-DD HH:MM 형식을 사용하세요."
    )


class Command(BaseCommand):
    help = "팝업 캠페인을 추가합니다. 앱에서 GET /trends/popup_campaigns/ 로 노출됩니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            required=True,
            help="팝업 제목",
        )
        parser.add_argument(
            "--image-url",
            required=True,
            help="팝업 이미지 URL",
        )
        parser.add_argument(
            "--instagram-url",
            required=True,
            help="인스타그램 링크 URL",
        )
        parser.add_argument(
            "--start-at",
            required=True,
            help="노출 시작일시 (YYYY-MM-DD 또는 YYYY-MM-DD HH:MM)",
        )
        parser.add_argument(
            "--end-at",
            required=True,
            help="노출 종료일시 (YYYY-MM-DD 또는 YYYY-MM-DD HH:MM)",
        )
        parser.add_argument(
            "--display-order",
            type=int,
            default=0,
            help="표시 순서 (작을수록 먼저, 기본값: 0)",
        )
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="비활성 상태로 생성 (기본값: 활성)",
        )

    def handle(self, *args, **options):
        start_at = parse_datetime(options["start_at"])
        end_at = parse_datetime(options["end_at"])

        if end_at <= start_at:
            raise CommandError("end_at은 start_at보다 이후여야 합니다.")

        popup = PopupCampaign.objects.create(
            title=options["title"],
            image_url=options["image_url"],
            instagram_url=options["instagram_url"],
            start_at=start_at,
            end_at=end_at,
            is_active=not options["inactive"],
            display_order=options["display_order"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"팝업 캠페인 생성 완료: id={popup.id}, title='{popup.title}'"
            )
        )
        self.stdout.write(
            f"  - 노출 기간: {popup.start_at} ~ {popup.end_at}"
        )
        self.stdout.write(
            f"  - API: GET /trends/popup_campaigns/ 에서 조회 가능"
        )
