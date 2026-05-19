"""
coupons DB의 RestaurantCouponBenefit·StampRewardRule 을 읽어
restaurants_affiliate.coupon_benefits_summary 컬럼을 채웁니다.

사용 예:
  python manage.py sync_restaurant_coupon_benefits_summary --dry-run
  python manage.py sync_restaurant_coupon_benefits_summary --restaurant-id 33
  python manage.py sync_restaurant_coupon_benefits_summary --all-affiliates
  python manage.py sync_restaurant_coupon_benefits_summary --all-affiliates --include-text
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from restaurants.affiliate_db import (
    AFFILIATE_TABLE,
    SUMMARY_COLUMN,
    ensure_affiliate_summary_column,
    resolve_affiliate_db_alias,
)
from restaurants.benefits_summary import (
    build_coupon_benefits_summary,
    format_coupon_benefits_summary_text,
)
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = (
        "신규가입·친구초대·스탬프 쿠폰 혜택을 DB에서 집계해 "
        "restaurants_affiliate.coupon_benefits_summary 에 반영합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            action="append",
            dest="restaurant_ids",
            help="대상 식당 ID (여러 번 지정 가능)",
        )
        parser.add_argument(
            "--all-affiliates",
            action="store_true",
            help="is_affiliate=TRUE 인 모든 제휴 식당 대상",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB 업데이트 없이 결과만 출력",
        )
        parser.add_argument(
            "--include-text",
            action="store_true",
            help="JSON과 함께 사람이 읽기 쉬운 요약 텍스트도 출력",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="출력·처리 건수 제한 (검수용)",
        )
        parser.add_argument(
            "--database",
            type=str,
            default=None,
            help="restaurants_affiliate DB alias (기본: 라우터 기준, 보통 cloudsql)",
        )

    def handle(self, *args, **options):
        restaurant_ids = options.get("restaurant_ids") or []
        all_affiliates = options["all_affiliates"]
        dry_run = options["dry_run"]
        include_text = options["include_text"]
        limit = options["limit"]

        if not restaurant_ids and not all_affiliates:
            raise CommandError(
                "--restaurant-id 또는 --all-affiliates 중 하나는 필요합니다."
            )

        alias = resolve_affiliate_db_alias(options.get("database"))
        conn = connections[alias]

        with conn.cursor() as cursor:
            table_names = conn.introspection.table_names(cursor)
            if AFFILIATE_TABLE not in table_names:
                raise CommandError(
                    f"DB({alias})에 {AFFILIATE_TABLE} 테이블이 없습니다. "
                    f"python manage.py migrate restaurants --database={alias} 를 실행하세요."
                )

        if not ensure_affiliate_summary_column(conn):
            raise CommandError(
                f"DB({alias})에 {SUMMARY_COLUMN} 컬럼이 없습니다. "
                f"python manage.py migrate restaurants --database={alias} 를 실행하세요. "
                "(restaurants 앱은 cloudsql 에 마이그레이션되어야 합니다.)"
            )

        if all_affiliates:
            qs = AffiliateRestaurant.objects.using(alias).filter(is_affiliate=True)
            restaurant_ids = list(qs.values_list("restaurant_id", flat=True))
        else:
            restaurant_ids = sorted(set(restaurant_ids))

        if limit:
            restaurant_ids = restaurant_ids[:limit]

        if not restaurant_ids:
            self.stdout.write("대상 식당이 없습니다.")
            return

        self.stdout.write(
            f"대상 {len(restaurant_ids)}곳 (db={alias}, dry_run={dry_run})"
        )

        updated = 0
        for rid in restaurant_ids:
            summary = build_coupon_benefits_summary(rid, db_alias=alias)
            text = format_coupon_benefits_summary_text(summary) if include_text else ""

            try:
                name = (
                    AffiliateRestaurant.objects.using(alias)
                    .filter(restaurant_id=rid)
                    .values_list("name", flat=True)
                    .first()
                )
            except Exception:
                name = None

            label = f"[{rid}] {name or '?'}"
            if dry_run:
                self.stdout.write(f"\n{label}")
                self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
                if include_text and text:
                    self.stdout.write("--- text ---")
                    self.stdout.write(text)
                continue

            payload = json.dumps(summary, ensure_ascii=False)
            with conn.cursor() as cursor:
                if conn.vendor == "postgresql":
                    cursor.execute(
                        """
                        UPDATE restaurants_affiliate
                        SET coupon_benefits_summary = %s::jsonb
                        WHERE restaurant_id = %s
                        """,
                        [payload, rid],
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE restaurants_affiliate
                        SET coupon_benefits_summary = %s
                        WHERE restaurant_id = %s
                        """,
                        [payload, rid],
                    )
                if cursor.rowcount:
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"✓ {label}"))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ {label} — restaurants_affiliate 행 없음")
                    )

            if include_text and text:
                self.stdout.write(text)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"\n완료: {updated}/{len(restaurant_ids)}곳 반영")
            )
