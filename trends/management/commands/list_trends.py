from django.core.management.base import BaseCommand

from trends.models import Trend


class Command(BaseCommand):
    help = (
        "저장된 트렌드(배너) 목록을 index와 함께 출력합니다. "
        "순서는 앱 노출 순서(display_order 오름차순, 동률 시 최신순)와 동일합니다."
    )

    def handle(self, *args, **options):
        trends = list(Trend.objects.all())
        total = len(trends)

        if total == 0:
            self.stdout.write("등록된 트렌드(배너)가 없습니다.")
            return

        self.stdout.write(self.style.SUCCESS(f"트렌드(배너) {total}건"))
        for index, trend in enumerate(trends, start=1):
            self.stdout.write(
                f"[{index}] id={trend.id} | {trend.title} | "
                f"display_order={trend.display_order}"
            )
        self.stdout.write(
            "상세 조회: python manage.py show_trend_by_display_index <index>"
        )
