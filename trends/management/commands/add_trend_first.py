from django.core.management.base import BaseCommand

from trends.models import Trend


class Command(BaseCommand):
    help = (
        "새 트렌드를 가장 앞(1번) 순서에 추가합니다. "
        "트렌드 리스트는 created_at 기준 내림차순으로 정렬되므로, "
        "이 명령어로 생성한 트렌드는 자동으로 1번 위치에 오게 됩니다."
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

    def handle(self, *args, **options):
        title = options["title"]
        description = options["description"]
        blog_link = options["blog_link"]
        image_path = options.get("image_path")

        trend = Trend(
            title=title,
            description=description,
            blog_link=blog_link,
        )

        # 이 프로젝트에서는 ImageField에 S3 URL 문자열을 직접 name으로 저장해서 사용하고 있음
        if image_path:
            trend.image.name = image_path

        trend.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"새 트렌드가 생성되었습니다. id={trend.id}, 제목='{trend.title}'"
            )
        )
        self.stdout.write(
            "리스트는 created_at 내림차순으로 정렬되므로, "
            "이 트렌드는 자동으로 1번(가장 앞) 트렌드가 됩니다."
        )




