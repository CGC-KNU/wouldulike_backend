from django.core.management.base import BaseCommand, CommandError

from trends.models import PopupCampaign


class Command(BaseCommand):
    help = (
        "팝업 캠페인 목록에서 특정 index의 상세 정보를 출력합니다. "
        "순서는 앱 노출 순서(display_order 오름차순, 동률 시 최신순)와 동일합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "index",
            type=int,
            help="조회할 팝업의 index (1부터 시작)",
        )

    def handle(self, *args, **options):
        index = options["index"]

        if index < 1:
            raise CommandError("index는 1 이상의 정수여야 합니다.")

        popups = list(PopupCampaign.objects.all())
        total = len(popups)

        if index > total:
            raise CommandError(
                f"index가 범위를 벗어났습니다. 현재 팝업 개수: {total}, 요청 index: {index}"
            )

        popup = popups[index - 1]

        self.stdout.write(self.style.SUCCESS(f"[{index}번째 팝업 캠페인]"))
        self.stdout.write(f"- id: {popup.id}")
        self.stdout.write(f"- 제목: {popup.title}")
        self.stdout.write(f"- display_order: {popup.display_order}")
        self.stdout.write(f"- is_active: {popup.is_active}")
        self.stdout.write(f"- image_url: {popup.image_url}")
        self.stdout.write(f"- instagram_url: {popup.instagram_url}")
        self.stdout.write(f"- start_at: {popup.start_at}")
        self.stdout.write(f"- end_at: {popup.end_at}")
        self.stdout.write(f"- created_at: {popup.created_at}")
        self.stdout.write(f"- updated_at: {popup.updated_at}")
