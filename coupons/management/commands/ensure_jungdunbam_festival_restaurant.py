from django.core.management.base import BaseCommand

from coupons.festival_jungdunbam import (
    MERCHANT_PIN,
    RESTAURANT_ID,
    RESTAURANT_NAME,
    ensure_jungdunbam_festival_data,
    resolve_cloudsql_alias,
)


class Command(BaseCommand):
    help = (
        "우주라이크 X 정든밤 축제 주막(restaurant_id=298) 데이터를 CloudSQL에 반영 "
        "(is_affiliate=TRUE). "
        "반영합니다. 배포 후 앱에 안 보일 때 수동 실행용."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            type=str,
            default=None,
            help="DB alias (기본: cloudsql, 없으면 default)",
        )

    def handle(self, *args, **options):
        alias = options.get("database") or resolve_cloudsql_alias()
        used = ensure_jungdunbam_festival_data(db_alias=alias)
        self.stdout.write(
            self.style.SUCCESS(
                f"완료: db={used}, restaurant_id={RESTAURANT_ID}, "
                f"name={RESTAURANT_NAME!r}, pin={MERCHANT_PIN}"
            )
        )
