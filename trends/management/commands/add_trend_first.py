from django.db.models import F
from django.core.management.base import BaseCommand, CommandError

from trends.models import Trend


class Command(BaseCommand):
    help = (
        "새 트렌드를 지정한 위치에 추가합니다. "
        "--position으로 1번(가장 앞), 2번, 3번... 위치를 지정할 수 있습니다. "
        "기본값은 1번(가장 앞)입니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--title",
            required=True,
            help="트렌드 제목",
        )
        parser.add_argument(
            "--description",
            required=True,
            help="트렌드 설명",
        )
        parser.add_argument(
            "--blog-link",
            required=True,
            help="연결할 블로그 링크(URL)",
        )
        parser.add_argument(
            "--image-path",
            required=False,
            help=(
                "이미지 경로 또는 URL. "
                "S3 URL을 직접 저장하는 경우 전체 URL을 넣어주세요."
            ),
        )
        parser.add_argument(
            "--position",
            type=int,
            default=1,
            help="추가할 위치 (1=가장 앞, 2=두 번째, ... 기본값: 1)",
        )

    def handle(self, *args, **options):
        title = options["title"]
        description = options["description"]
        blog_link = options["blog_link"]
        image_path = options.get("image_path")
        position = options["position"]

        if position < 1:
            raise CommandError("--position은 1 이상이어야 합니다.")

        # 해당 위치 이후의 트렌드들 display_order +1
        target_display_order = position - 1  # 1번 → 0, 2번 → 1, ...
        Trend.objects.filter(display_order__gte=target_display_order).update(
            display_order=F("display_order") + 1
        )

        trend = Trend(
            title=title,
            description=description,
            blog_link=blog_link,
            display_order=target_display_order,
        )

        # S3 전체 URL을 직접 저장 (ImageField의 name에 문자열 저장)
        if image_path:
            trend.image = image_path

        trend.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"새 트렌드가 {position}번 위치에 생성되었습니다. id={trend.id}, 제목='{trend.title}'"
            )
        )











