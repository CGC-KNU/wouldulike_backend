from django.core.management.base import BaseCommand, CommandError

from trends.models import Trend


class Command(BaseCommand):
    help = (
        "트렌드 리스트에서 특정 순서(인덱스)의 트렌드를 확인합니다. "
        "순서는 created_at 기준 내림차순(가장 최신이 1번)입니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "index",
            type=int,
            help="조회할 트렌드의 순서 (1부터 시작, 최신이 1번)",
        )

    def handle(self, *args, **options):
        index = options["index"]

        if index < 1:
            raise CommandError("index는 1 이상의 정수여야 합니다.")

        queryset = Trend.objects.all().order_by("-created_at")
        total = queryset.count()

        if index > total:
            raise CommandError(
                f"index가 범위를 벗어났습니다. 현재 트렌드 개수: {total}, 요청 index: {index}"
            )

        trend = queryset[index - 1]

        self.stdout.write(self.style.SUCCESS(f"[{index}번째 트렌드 정보]"))
        self.stdout.write(f"- id: {trend.id}")
        self.stdout.write(f"- 제목: {trend.title}")
        self.stdout.write(f"- 설명: {trend.description}")
        self.stdout.write(f"- 블로그 링크: {trend.blog_link}")
        self.stdout.write(f"- 이미지 name: {trend.image.name if trend.image else '없음'}")
        self.stdout.write(f"- created_at: {trend.created_at}")
        self.stdout.write(f"- updated_at: {trend.updated_at}")









