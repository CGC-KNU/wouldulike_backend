"""축제 주막 restaurant_id 298→299 이전 (CloudSQL 수동 보정용)."""

from django.core.management.base import BaseCommand

from coupons.festival_jungdunbam import (
    LEGACY_FESTIVAL_RESTAURANT_ID,
    RESTAURANT_ID,
    reassign_festival_restaurant_id,
    resolve_cloudsql_alias,
)
from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data


class Command(BaseCommand):
    help = (
        f"우주라이크 X 정든밤 축제 주막 ID를 {LEGACY_FESTIVAL_RESTAURANT_ID} → "
        f"{RESTAURANT_ID} 로 이전합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="cloudsql",
            help="DB alias (default: cloudsql)",
        )

    def handle(self, *args, **options):
        alias = options["database"] or resolve_cloudsql_alias()
        reassign_festival_restaurant_id(db_alias=alias)
        ensure_pub_jujeom_event_data(db_alias=alias)
        self.stdout.write(
            self.style.SUCCESS(
                f"완료: restaurant_id {LEGACY_FESTIVAL_RESTAURANT_ID} → {RESTAURANT_ID} ({alias})"
            )
        )
