"""
쿠폰 사용량 통계를 확인하는 명령어

전체 쿠폰 사용량과 식당별 쿠폰 사용량을 조회합니다.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import router

from coupons.models import Coupon
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "쿠폰 사용량 통계를 확인합니다. 전체 사용량과 식당별 사용량을 조회할 수 있습니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--by-restaurant",
            action="store_true",
            help="식당별 쿠폰 사용량을 상세히 표시",
        )
        parser.add_argument(
            "--restaurant-id",
            type=int,
            help="특정 식당 ID의 쿠폰 사용량만 조회",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["ISSUED", "REDEEMED", "EXPIRED", "CANCELED"],
            help="특정 상태의 쿠폰만 조회 (기본값: 전체)",
        )

    def handle(self, *args, **options):
        alias = router.db_for_read(Coupon)
        by_restaurant = options.get("by_restaurant", False)
        restaurant_id = options.get("restaurant_id")
        status_filter = options.get("status")

        # 기본 쿼리셋
        coupon_qs = Coupon.objects.using(alias)

        # 상태 필터 적용
        if status_filter:
            coupon_qs = coupon_qs.filter(status=status_filter)

        # 식당 ID 필터 적용
        if restaurant_id:
            coupon_qs = coupon_qs.filter(restaurant_id=restaurant_id)

        # 전체 통계
        total_count = coupon_qs.count()
        status_counts = (
            coupon_qs.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        self.stdout.write(self.style.SUCCESS("\n=== 쿠폰 사용량 통계 ===\n"))
        self.stdout.write(f"전체 쿠폰 수: {total_count:,}개")
        if status_filter:
            self.stdout.write(f"필터: 상태 = {status_filter}")
        if restaurant_id:
            self.stdout.write(f"필터: 식당 ID = {restaurant_id}")

        self.stdout.write("\n상태별 통계:")
        for item in status_counts:
            status_name = item["status"]
            count = item["count"]
            percentage = (count / total_count * 100) if total_count > 0 else 0
            self.stdout.write(
                f"  - {status_name}: {count:,}개 ({percentage:.1f}%)"
            )

        # 사용된 쿠폰 (REDEEMED) 상세 정보
        redeemed_count = coupon_qs.filter(status="REDEEMED").count()
        if redeemed_count > 0:
            self.stdout.write(f"\n사용된 쿠폰 (REDEEMED): {redeemed_count:,}개")

        # 식당별 통계
        if by_restaurant or restaurant_id:
            self.stdout.write("\n=== 식당별 쿠폰 통계 ===\n")

            # 식당별 쿼리
            restaurant_qs = coupon_qs.exclude(restaurant_id__isnull=True)

            if restaurant_id:
                # 특정 식당만 조회
                restaurant_stats = (
                    restaurant_qs.values("restaurant_id")
                    .annotate(
                        total=Count("id"),
                        redeemed=Count("id", filter=Q(status="REDEEMED")),
                        issued=Count("id", filter=Q(status="ISSUED")),
                        expired=Count("id", filter=Q(status="EXPIRED")),
                        canceled=Count("id", filter=Q(status="CANCELED")),
                    )
                    .order_by("-redeemed", "-total")
                )
            else:
                # 모든 식당 조회
                restaurant_stats = (
                    restaurant_qs.values("restaurant_id")
                    .annotate(
                        total=Count("id"),
                        redeemed=Count("id", filter=Q(status="REDEEMED")),
                        issued=Count("id", filter=Q(status="ISSUED")),
                        expired=Count("id", filter=Q(status="EXPIRED")),
                        canceled=Count("id", filter=Q(status="CANCELED")),
                    )
                    .order_by("-redeemed", "-total")
                )

            # 식당 이름 조회를 위한 캐시
            restaurant_alias = router.db_for_read(AffiliateRestaurant)
            restaurant_ids = [item["restaurant_id"] for item in restaurant_stats]
            restaurant_names = {}
            if restaurant_ids:
                try:
                    restaurants = AffiliateRestaurant.objects.using(restaurant_alias).filter(
                        restaurant_id__in=restaurant_ids
                    )
                    restaurant_names = {
                        r.restaurant_id: r.name for r in restaurants
                    }
                except Exception:
                    pass

            # 결과 출력
            if restaurant_id:
                # 특정 식당 상세 정보
                if restaurant_stats:
                    item = restaurant_stats[0]
                    rid = item["restaurant_id"]
                    name = restaurant_names.get(rid, "N/A")
                    self.stdout.write(f"식당 ID: {rid}")
                    self.stdout.write(f"식당명: {name}")
                    self.stdout.write(f"  - 전체: {item['total']:,}개")
                    self.stdout.write(f"  - 사용됨 (REDEEMED): {item['redeemed']:,}개")
                    self.stdout.write(f"  - 발급됨 (ISSUED): {item['issued']:,}개")
                    self.stdout.write(f"  - 만료됨 (EXPIRED): {item['expired']:,}개")
                    self.stdout.write(f"  - 취소됨 (CANCELED): {item['canceled']:,}개")
                    if item['total'] > 0:
                        usage_rate = (item['redeemed'] / item['total'] * 100)
                        self.stdout.write(f"  - 사용률: {usage_rate:.1f}%")
                else:
                    self.stdout.write(self.style.WARNING(f"식당 ID {restaurant_id}에 대한 쿠폰 데이터가 없습니다."))
            else:
                # 모든 식당 요약 정보
                self.stdout.write("식당별 쿠폰 사용량 (사용된 쿠폰 수 기준 정렬):\n")
                for idx, item in enumerate(restaurant_stats[:50], 1):  # 상위 50개만 표시
                    rid = item["restaurant_id"]
                    name = restaurant_names.get(rid, "N/A")
                    self.stdout.write(
                        f"{idx:3d}. 식당 ID {rid:4d} ({name[:30]:30s}) - "
                        f"전체: {item['total']:5d}개, "
                        f"사용됨: {item['redeemed']:5d}개, "
                        f"발급됨: {item['issued']:5d}개"
                    )
                    if item['total'] > 0:
                        usage_rate = (item['redeemed'] / item['total'] * 100)
                        self.stdout.write(f"      사용률: {usage_rate:.1f}%")

                if len(restaurant_stats) > 50:
                    self.stdout.write(f"\n... 외 {len(restaurant_stats) - 50}개 식당 더 있습니다.")

        self.stdout.write("")

