from django.core.management.base import BaseCommand, CommandError

from trends.models import Trend


class Command(BaseCommand):
    help = (
        "트렌드(배너) 목록에서 특정 index의 상세 정보를 출력합니다. "
        "순서는 앱 노출 순서(display_order 오름차순, 동률 시 최신순)와 동일합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "index",
            type=int,
            help="조회할 트렌드의 index (1부터 시작)",
        )

    def handle(self, *args, **options):
        index = options["index"]

        if index < 1:
            raise CommandError("index는 1 이상의 정수여야 합니다.")

        trends = list(Trend.objects.all())
        total = len(trends)

        if index > total:
            raise CommandError(
                f"index가 범위를 벗어났습니다. 현재 트렌드 개수: {total}, 요청 index: {index}"
            )

        trend = trends[index - 1]

        self.stdout.write(self.style.SUCCESS(f"[{index}번째 트렌드(배너)]"))
        self.stdout.write(f"- id: {trend.id}")
        self.stdout.write(f"- 제목: {trend.title}")
        self.stdout.write(f"- 설명: {trend.description}")
        self.stdout.write(f"- display_order: {trend.display_order}")
        self.stdout.write(f"- blog_link: {trend.blog_link}")
        self.stdout.write(f"- 이미지: {trend.image}")
        self.stdout.write(f"- created_at: {trend.created_at}")
        self.stdout.write(f"- updated_at: {trend.updated_at}")
