"""
전체 쿠폰 발급/사용량 및 식당별 누적 지표를 조회하는 명령어

- 전체(누적) 쿠폰 발급/사용 현황
- 식당별로 신규가입/친구초대/스탬프/이벤트별 발급·사용·사용률
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import router

from coupons.models import Coupon
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "전체 쿠폰 발급/사용량 및 식당별 누적 지표를 조회합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            help="특정 식당 ID만 조회",
        )

    def _format_rate(self, issued: int, redeemed: int) -> str:
        """발급/사용 건수로 사용률 문자열 생성"""
        if issued <= 0:
            return "0.0%"
        return f"{(redeemed / issued * 100):.1f}%"

    def _print_restaurant_blocks(self, coupon_qs, *, restaurant_id=None):
        """
        식당별로 누적 쿠폰 통계를 출력합니다.

        - 신규가입(WELCOME_3000)
        - 친구초대(REFERRAL_BONUS_REFERRER / REFERRAL_BONUS_REFEREE)
        - 스탬프(STAMP_REWARD_5 / STAMP_REWARD_10)
        - 이벤트별(기타 캠페인 코드)
        """
        bar = "===================================="
        sep = "--------------------------------------------"

        restaurant_alias = router.db_for_read(AffiliateRestaurant)
        restaurant_qs = AffiliateRestaurant.objects.using(restaurant_alias)
        if restaurant_id:
            restaurant_qs = restaurant_qs.filter(restaurant_id=restaurant_id)

        restaurants = list(
            restaurant_qs.values("restaurant_id", "name").order_by("restaurant_id")
        )

        if not restaurants:
            self.stdout.write("조회할 제휴 식당이 없습니다.")
            self.stdout.write("")
            self.stdout.write(bar)
            return

        for r in restaurants:
            rid = r["restaurant_id"]
            name = r["name"] or "N/A"

            restaurant_coupons = coupon_qs.filter(restaurant_id=rid)

            # 해당 식당에 쿠폰이 하나도 없다면 스킵
            if not restaurant_coupons.exists():
                continue

            # --- 기본 타입별 집계 ---
            # 신규가입 (WELCOME_3000)
            signup_qs = restaurant_coupons.filter(
                coupon_type__code="WELCOME_3000"
            )
            signup_issued = signup_qs.count()
            signup_used = signup_qs.filter(status="REDEEMED").count()

            # 친구초대 (REFERRAL_BONUS_REFERRER / REFERRAL_BONUS_REFEREE)
            referral_qs = restaurant_coupons.filter(
                coupon_type__code__in=[
                    "REFERRAL_BONUS_REFERRER",
                    "REFERRAL_BONUS_REFEREE",
                ]
            )
            referral_issued = referral_qs.count()
            referral_used = referral_qs.filter(status="REDEEMED").count()

            # 스탬프 5개 (STAMP_REWARD_5)
            stamp5_qs = restaurant_coupons.filter(
                coupon_type__code="STAMP_REWARD_5"
            )
            stamp5_issued = stamp5_qs.count()
            stamp5_used = stamp5_qs.filter(status="REDEEMED").count()

            # 스탬프 10개 (STAMP_REWARD_10)
            stamp10_qs = restaurant_coupons.filter(
                coupon_type__code="STAMP_REWARD_10"
            )
            stamp10_issued = stamp10_qs.count()
            stamp10_used = stamp10_qs.filter(status="REDEEMED").count()

            # 해당 식당에 집계할 항목이 하나도 없으면 스킵
            if (
                signup_issued == signup_used == 0
                and referral_issued == referral_used == 0
                and stamp5_issued == stamp5_used == 0
                and stamp10_issued == stamp10_used == 0
            ):
                # 혹시 다른 이벤트성 쿠폰만 있는 경우를 위해 아래 이벤트 섹션은 그대로 진행
                has_any_event = restaurant_coupons.exclude(
                    campaign__isnull=True
                ).exclude(campaign__code__in=["SIGNUP_WELCOME", "REFERRAL"]).exists()
                if not has_any_event:
                    continue

            self.stdout.write(f"🍽️  식당 ID {rid}: {name}")
            self.stdout.write(sep)

            if signup_issued > 0 or signup_used > 0:
                self.stdout.write(
                    f"  신규가입: 발급 {signup_issued}개 / 사용 {signup_used}개 "
                    f"({self._format_rate(signup_issued, signup_used)})"
                )
            if referral_issued > 0 or referral_used > 0:
                self.stdout.write(
                    f"  친구초대: 발급 {referral_issued}개 / 사용 {referral_used}개 "
                    f"({self._format_rate(referral_issued, referral_used)})"
                )
            if stamp5_issued > 0 or stamp5_used > 0:
                self.stdout.write(
                    f"  스탬프 5개: 발급 {stamp5_issued}개 / 사용 {stamp5_used}개 "
                    f"({self._format_rate(stamp5_issued, stamp5_used)})"
                )
            if stamp10_issued > 0 or stamp10_used > 0:
                self.stdout.write(
                    f"  스탬프 10개: 발급 {stamp10_issued}개 / 사용 {stamp10_used}개 "
                    f"({self._format_rate(stamp10_issued, stamp10_used)})"
                )

            # --- 이벤트별(캠페인별) 집계 ---
            event_qs = (
                restaurant_coupons.exclude(campaign__isnull=True)
                .exclude(campaign__code__in=["SIGNUP_WELCOME", "REFERRAL"])
            )

            event_stats = (
                event_qs.values("campaign__code", "campaign__name")
                .annotate(
                    issued=Count("id"),
                    used=Count("id", filter=Q(status="REDEEMED")),
                )
                .order_by("campaign__code")
            )

            if event_stats:
                self.stdout.write("")
                self.stdout.write("  이벤트별:")
                for item in event_stats:
                    camp_code = item["campaign__code"] or "N/A"
                    camp_name = item["campaign__name"] or "N/A"
                    issued = item["issued"]
                    used = item["used"]
                    rate = self._format_rate(issued, used)
                    self.stdout.write(
                        f"    - {camp_name} ({camp_code}): "
                        f"발급 {issued}개 / 사용 {used}개 ({rate})"
                    )

            self.stdout.write("")

        self.stdout.write(bar)
        self.stdout.write("")

    def handle(self, *args, **options):
        alias = router.db_for_read(Coupon)
        restaurant_id = options.get("restaurant_id")

        coupon_qs = Coupon.objects.using(alias).all()

        total_count = coupon_qs.count()
        redeemed_count = coupon_qs.filter(status="REDEEMED").count()
        overall_rate = self._format_rate(total_count, redeemed_count)

        bar = "===================================="

        self.stdout.write(bar)
        self.stdout.write("")
        self.stdout.write("전체 쿠폰 발급/사용량 및 식당별 누적 통계 (누적)")
        self.stdout.write("")
        self.stdout.write(bar)
        self.stdout.write("")

        self.stdout.write(f"전체 발급된 쿠폰 수: {total_count:,}개")
        self.stdout.write(f"전체 사용된 쿠폰 수: {redeemed_count:,}개")
        self.stdout.write(f"전체 사용률: {overall_rate}")
        self.stdout.write("")

        # 상태별 통계
        status_counts = (
            coupon_qs.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        self.stdout.write("상태별 통계:")
        for item in status_counts:
            status_name = item["status"]
            count = item["count"]
            rate = self._format_rate(total_count, count)
            self.stdout.write(f"  - {status_name}: {count:,}개 ({rate})")

        self.stdout.write("")

        # 식당별 누적 지표
        self.stdout.write("식당별 누적 지표:")
        self.stdout.write("")

        self._print_restaurant_blocks(coupon_qs, restaurant_id=restaurant_id)


