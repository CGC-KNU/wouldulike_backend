"""
특정 날짜에 발급된 쿠폰 내역을 확인하는 명령어

날짜별로 쿠폰 발급 내역을 조회하고 통계를 확인할 수 있습니다.
"""

from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.db import router
from django.utils import timezone

from coupons.models import Coupon, CouponType, Campaign
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "특정 날짜에 발급된 쿠폰 내역을 확인합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="조회할 날짜 (YYYY-MM-DD 형식, 여러 날짜는 쉼표로 구분)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="조회 시작 날짜 (YYYY-MM-DD 형식, --end-date와 함께 사용)",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="조회 종료 날짜 (YYYY-MM-DD 형식, --start-date와 함께 사용)",
        )
        parser.add_argument(
            "--by-restaurant",
            action="store_true",
            help="식당별로 그룹화하여 표시",
        )
        parser.add_argument(
            "--by-type",
            action="store_true",
            help="쿠폰 타입별로 그룹화하여 표시",
        )
        parser.add_argument(
            "--by-status",
            action="store_true",
            help="상태별로 그룹화하여 표시",
        )
        parser.add_argument(
            "--restaurant-id",
            type=int,
            help="특정 식당 ID만 조회",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="표시할 쿠폰 개수 제한 (기본값: 100)",
        )
        parser.add_argument(
            "--export",
            action="store_true",
            help="상세 내역을 CSV 형식으로 출력",
        )

    def parse_date(self, date_str):
        """날짜 문자열을 date 객체로 변환"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"날짜 형식이 올바르지 않습니다: {date_str} (YYYY-MM-DD 형식 사용)")

    def _format_rate(self, issued: int, redeemed: int) -> str:
        """발급/사용 건수로 사용률 문자열 생성"""
        if issued <= 0:
            return "0.0%"
        return f"{(redeemed / issued * 100):.1f}%"

    def _print_detailed_restaurant_report(self, coupon_qs, start_date, end_date, *, restaurant_id=None):
        """
        예시에 나왔던 포맷:

        - 기간별 식당별 쿠폰 타입별 발급량 및 사용량 통계
        - 식당별로 신규가입 / 친구초대 / 스탬프 5개 / 스탬프 10개
        - 이벤트별(캠페인별) 발급/사용 현황
        """
        # 구분선 길이는 운영에서 보기 좋게 고정 길이로 사용
        bar = "===================================="
        sep = "--------------------------------------------"

        # 헤더
        self.stdout.write(bar)
        self.stdout.write("")
        self.stdout.write(
            f"기간별 식당별 쿠폰 타입별 발급량 및 사용량 통계 "
            f"({start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')})"
        )
        self.stdout.write("")
        self.stdout.write(bar)
        self.stdout.write("")

        self.stdout.write(
            f"📅 기간: {start_date.strftime('%m.%d')} ~ {end_date.strftime('%m.%d')}"
        )
        self.stdout.write(sep)
        self.stdout.write("")

        # 대상 식당 목록 조회
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

        for idx, r in enumerate(restaurants, 1):
            rid = r["restaurant_id"]
            name = r["name"] or "N/A"

            restaurant_coupons = coupon_qs.filter(restaurant_id=rid)

            # 해당 기간에 발급/사용된 쿠폰이 전혀 없는 경우: 아예 출력하지 않음
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

            self.stdout.write(f"🍽️  식당 ID {rid}: {name}")
            self.stdout.write(sep)
            # 발급/사용 내역이 있는 타입만 출력
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
            # 기본 신규가입/친구초대 캠페인(SIGNUP_WELCOME, REFERRAL)은 제외하고,
            # 기말고사/이벤트 리워드 등 추가 이벤트만 집계
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
        
        # 날짜 파라미터 처리
        date_str = options.get("date")
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        
        if not date_str and not (start_date_str and end_date_str):
            raise CommandError("--date 또는 --start-date/--end-date를 지정해주세요.")
        
        if date_str and (start_date_str or end_date_str):
            raise CommandError("--date와 --start-date/--end-date를 동시에 사용할 수 없습니다.")
        
        # 날짜 범위 설정
        if date_str:
            # 여러 날짜를 쉼표로 구분
            date_list = [d.strip() for d in date_str.split(",")]
            dates = [self.parse_date(d) for d in date_list]
            if len(dates) == 1:
                start_date = dates[0]
                end_date = dates[0]
            else:
                start_date = min(dates)
                end_date = max(dates)
        else:
            start_date = self.parse_date(start_date_str)
            end_date = self.parse_date(end_date_str)
        
        if start_date > end_date:
            raise CommandError("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
        
        # 시간 범위 설정 (하루 전체)
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )
        
        # 쿠폰 쿼리
        coupon_qs = Coupon.objects.using(alias).filter(
            issued_at__gte=start_datetime,
            issued_at__lte=end_datetime,
        )
        
        # 식당 필터
        restaurant_id = options.get("restaurant_id")
        if restaurant_id:
            coupon_qs = coupon_qs.filter(restaurant_id=restaurant_id)
        
        # 전체 통계
        total_count = coupon_qs.count()

        # 예전 리포트 스타일(기간별 식당별 쿠폰 타입별 발급/사용 통계) 포맷
        # - by_restaurant 옵션이 지정되면 이 포맷으로 출력
        if options.get("by_restaurant"):
            if total_count == 0:
                self.stdout.write("해당 기간에 발급된 쿠폰이 없습니다.")
                return

            self._print_detailed_restaurant_report(
                coupon_qs, start_date, end_date, restaurant_id=restaurant_id
            )
            return

        self.stdout.write(self.style.SUCCESS("\n=== 쿠폰 발급 내역 ===\n"))
        if start_date == end_date:
            self.stdout.write(f"조회 날짜: {start_date.strftime('%Y년 %m월 %d일')}")
        else:
            self.stdout.write(
                f"조회 기간: {start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
            )
        if restaurant_id:
            self.stdout.write(f"식당 ID 필터: {restaurant_id}")
        self.stdout.write(f"총 발급된 쿠폰 수: {total_count:,}개\n")
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING("해당 기간에 발급된 쿠폰이 없습니다."))
            return
        
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
            percentage = (count / total_count * 100) if total_count > 0 else 0
            self.stdout.write(f"  - {status_name}: {count:,}개 ({percentage:.1f}%)")
        
        # 쿠폰 타입별 통계
        if options.get("by_type"):
            self.stdout.write("\n쿠폰 타입별 통계:")
            type_counts = (
                coupon_qs.values("coupon_type__code", "coupon_type__title")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            for item in type_counts:
                code = item["coupon_type__code"] or "N/A"
                title = item["coupon_type__title"] or "N/A"
                count = item["count"]
                self.stdout.write(f"  - {code} ({title}): {count:,}개")
        
        # 식당별 통계
        if options.get("by_restaurant"):
            self.stdout.write("\n식당별 통계:")
            
            restaurant_alias = router.db_for_read(AffiliateRestaurant)
            restaurant_stats = (
                coupon_qs.exclude(restaurant_id__isnull=True)
                .values("restaurant_id")
                .annotate(
                    total=Count("id"),
                    redeemed=Count("id", filter=Q(status="REDEEMED")),
                )
                .order_by("-total")
            )
            
            # 식당 이름 조회
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
            
            for item in restaurant_stats[:50]:  # 상위 50개만 표시
                rid = item["restaurant_id"]
                name = restaurant_names.get(rid, "N/A")
                self.stdout.write(
                    f"  - 식당 ID {rid:4d} ({name[:30]:30s}): "
                    f"전체 {item['total']:5d}개, "
                    f"사용됨 {item['redeemed']:5d}개"
                )
            
            if len(restaurant_stats) > 50:
                self.stdout.write(f"  ... 외 {len(restaurant_stats) - 50}개 식당 더 있습니다.")
        
        # 상세 내역
        limit = options.get("limit", 100)
        self.stdout.write(f"\n상세 내역 (최대 {limit}개):")
        
        # 쿠폰 타입 및 캠페인 정보를 가져오기 위해 select_related 사용
        coupons = (
            coupon_qs.select_related("coupon_type", "campaign")
            .order_by("-issued_at")[:limit]
        )
        
        # 식당 이름 캐시
        restaurant_ids = set(c.restaurant_id for c in coupons if c.restaurant_id)
        restaurant_names = {}
        if restaurant_ids:
            restaurant_alias = router.db_for_read(AffiliateRestaurant)
            try:
                restaurants = AffiliateRestaurant.objects.using(restaurant_alias).filter(
                    restaurant_id__in=restaurant_ids
                )
                restaurant_names = {r.restaurant_id: r.name for r in restaurants}
            except Exception:
                pass
        
        for idx, coupon in enumerate(coupons, 1):
            restaurant_name = "N/A"
            if coupon.restaurant_id:
                restaurant_name = restaurant_names.get(
                    coupon.restaurant_id,
                    coupon.benefit_snapshot.get("restaurant_name") if coupon.benefit_snapshot else "N/A"
                )
            
            coupon_type_code = coupon.coupon_type.code if coupon.coupon_type else "N/A"
            campaign_code = coupon.campaign.code if coupon.campaign else "N/A"
            
            self.stdout.write(
                f"{idx:4d}. [{coupon.issued_at.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"코드: {coupon.code:12s} | "
                f"상태: {coupon.status:10s} | "
                f"타입: {coupon_type_code:20s} | "
                f"식당: {restaurant_name[:20]:20s} | "
                f"캠페인: {campaign_code}"
            )
        
        if total_count > limit:
            self.stdout.write(f"\n... 외 {total_count - limit}개 쿠폰 더 있습니다.")
        
        self.stdout.write("")

