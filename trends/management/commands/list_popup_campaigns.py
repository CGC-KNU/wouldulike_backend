from django.core.management.base import BaseCommand

from trends.models import PopupCampaign


class Command(BaseCommand):
    help = (
        "저장된 팝업 캠페인 목록을 index와 함께 출력합니다. "
        "순서는 앱 노출 순서(display_order 오름차순, 동률 시 최신순)와 동일합니다."
    )

    def handle(self, *args, **options):
        popups = list(PopupCampaign.objects.all())
        total = len(popups)

        if total == 0:
            self.stdout.write("등록된 팝업 캠페인이 없습니다.")
            return

        self.stdout.write(self.style.SUCCESS(f"팝업 캠페인 {total}건"))
        for index, popup in enumerate(popups, start=1):
            active_label = "활성" if popup.is_active else "비활성"
            self.stdout.write(
                f"[{index}] id={popup.id} | {popup.title} | "
                f"display_order={popup.display_order} | {active_label} | "
                f"{popup.start_at} ~ {popup.end_at}"
            )
        self.stdout.write(
            "상세 조회: python manage.py show_popup_campaign_by_index <index>"
        )
