from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import router
from django.db.models import Count
from django.utils import timezone

from coupons.models import Coupon


class Command(BaseCommand):
    help = "특정 연도 이전에 발급된 쿠폰 수를 조회합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=2026,
            help="기준 연도 (기본값: 2026). 해당 연도 1월 1일 이전 발급 쿠폰을 집계합니다.",
        )
        parser.add_argument(
            "--by-status",
            action="store_true",
            help="상태별 건수를 함께 출력합니다.",
        )
        parser.add_argument(
            "--by-type",
            action="store_true",
            help="쿠폰 타입별 건수를 함께 출력합니다.",
        )

    def handle(self, *args, **options):
        year = options["year"]
        alias = router.db_for_read(Coupon)
        cutoff = timezone.make_aware(datetime(year, 1, 1, 0, 0, 0))

        base_qs = Coupon.objects.using(alias).filter(issued_at__lt=cutoff)
        total_count = base_qs.count()

        self.stdout.write("")
        self.stdout.write("====================================")
        self.stdout.write(f"{year}년 이전 쿠폰 발급량")
        self.stdout.write("====================================")
        self.stdout.write(f"기준 시각: {cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        self.stdout.write(f"총 발급량: {total_count:,}개")

        if options["by_status"]:
            self.stdout.write("")
            self.stdout.write("상태별 건수:")
            status_rows = (
                base_qs.values("status")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for row in status_rows:
                self.stdout.write(f"  - {row['status']}: {row['count']:,}개")

        if options["by_type"]:
            self.stdout.write("")
            self.stdout.write("쿠폰 타입별 건수:")
            type_rows = (
                base_qs.values("coupon_type__code", "coupon_type__title")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for row in type_rows:
                code = row["coupon_type__code"] or "N/A"
                title = row["coupon_type__title"] or "N/A"
                self.stdout.write(f"  - {code} ({title}): {row['count']:,}개")

        self.stdout.write("")
