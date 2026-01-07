"""
기간별 식당별 쿠폰 타입별 발급량 및 사용량 통계를 확인하는 명령어

각 식당별로 신규가입, 친구초대, 이벤트별, 스탬프 5개, 스탬프 10개 쿠폰의 발급량과 사용량을
기간별로 확인할 수 있습니다.
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, F
from django.db import router
from django.utils import timezone

from coupons.models import Coupon, CouponType, Campaign
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "기간별 식당별 쿠폰 타입별 발급량 및 사용량 통계를 확인합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=2024,
            help="조회할 연도 (기본값: 2024)",
        )
        parser.add_argument(
            "--month",
            type=int,
            default=12,
            help="조회할 월 (기본값: 12)",
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
            "--restaurant-id",
            type=int,
            help="특정 식당 ID만 조회",
        )
        parser.add_argument(
            "--coupon-type",
            type=str,
            help="특정 쿠폰 타입 코드만 조회",
        )

    def handle(self, *args, **options):
        year = options.get("year", 2024)
        month = options.get("month", 12)
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        restaurant_id = options.get("restaurant_id")
        coupon_type_code = options.get("coupon_type")

        alias = router.db_for_read(Coupon)

        # 기간 설정
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                periods = [
                    {
                        "name": f"{start_date_str} ~ {end_date_str}",
                        "start": start_date,
                        "end": end_date,
                    }
                ]
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요.")
                )
                return
        else:
            # 기본값: 12월의 주차별 기간
            periods = self._get_default_periods(year, month)

        # 쿠폰 타입 정의
        coupon_type_groups = {
            "신규가입": ["WELCOME_3000"],
            "친구초대": ["REFERRAL_BONUS_REFEREE"],
            "스탬프 5개": ["STAMP_REWARD_5"],
            "스탬프 10개": ["STAMP_REWARD_10"],
            "이벤트별": self._get_event_campaigns(alias),
        }

        # 식당 목록 가져오기
        restaurant_alias = router.db_for_read(AffiliateRestaurant)
        if restaurant_id:
            try:
                restaurants = [
                    AffiliateRestaurant.objects.using(restaurant_alias).get(
                        restaurant_id=restaurant_id
                    )
                ]
            except AffiliateRestaurant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"식당 ID {restaurant_id}를 찾을 수 없습니다.")
                )
                return
        else:
            restaurants = list(
                AffiliateRestaurant.objects.using(restaurant_alias).all().order_by(
                    "restaurant_id"
                )
            )

        # 결과 출력
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 100))
        self.stdout.write(
            self.style.SUCCESS(f"기간별 식당별 쿠폰 타입별 발급량 및 사용량 통계 ({year}년 {month}월)")
        )
        self.stdout.write(self.style.SUCCESS("=" * 100 + "\n"))

        # 각 기간별로 통계 출력
        for period in periods:
            self.stdout.write(
                self.style.WARNING(f"\n📅 기간: {period['name']}")
            )
            self.stdout.write("-" * 100)

            # 각 식당별로 통계 출력
            for restaurant in restaurants:
                rid = restaurant.restaurant_id
                name = restaurant.name

                self.stdout.write(f"\n🍽️  식당 ID {rid}: {name}")
                self.stdout.write("-" * 80)

                # 각 쿠폰 타입 그룹별로 통계 출력
                has_any_data = False
                for group_name, type_codes_or_campaigns in coupon_type_groups.items():
                    if group_name == "이벤트별":
                        # 이벤트별은 Campaign으로 구분
                        issued_count = self._get_event_issued_count(
                            alias,
                            rid,
                            period["start"],
                            period["end"],
                            type_codes_or_campaigns,
                        )
                        usage_count = self._get_event_usage_count(
                            alias,
                            rid,
                            period["start"],
                            period["end"],
                            type_codes_or_campaigns,
                        )
                        
                        if issued_count or usage_count:
                            has_any_data = True
                            campaign_details = []
                            # 발급량과 사용량을 함께 표시
                            for campaign_code in set(list(issued_count.keys()) + list(usage_count.keys())):
                                issued = issued_count.get(campaign_code, 0)
                                used = usage_count.get(campaign_code, 0)
                                try:
                                    campaign = Campaign.objects.using(alias).get(
                                        code=campaign_code
                                    )
                                    campaign_name = campaign.name
                                except Campaign.DoesNotExist:
                                    campaign_name = campaign_code
                                
                                usage_rate = (used / issued * 100) if issued > 0 else 0
                                campaign_details.append(
                                    f"{campaign_name} ({campaign_code}): 발급 {issued}개 / 사용 {used}개 ({usage_rate:.1f}%)"
                                )
                            if campaign_details:
                                self.stdout.write(
                                    f"  {group_name}:"
                                )
                                for detail in campaign_details:
                                    self.stdout.write(f"    - {detail}")
                        elif not type_codes_or_campaigns:
                            # 이벤트 Campaign이 없는 경우
                            self.stdout.write(f"  {group_name}: (이벤트 없음)")
                    else:
                        # 일반 쿠폰 타입
                        issued_count = self._get_coupon_type_issued_count(
                            alias,
                            rid,
                            period["start"],
                            period["end"],
                            type_codes_or_campaigns,
                        )
                        usage_count = self._get_coupon_type_usage_count(
                            alias,
                            rid,
                            period["start"],
                            period["end"],
                            type_codes_or_campaigns,
                        )
                        
                        if issued_count > 0 or usage_count > 0:
                            has_any_data = True
                        
                        usage_rate = (usage_count / issued_count * 100) if issued_count > 0 else 0
                        self.stdout.write(
                            f"  {group_name}: 발급 {issued_count}개 / 사용 {usage_count}개 ({usage_rate:.1f}%)"
                        )
                
                # 데이터가 하나도 없는 경우 표시
                if not has_any_data:
                    self.stdout.write("  (해당 기간에 발급/사용된 쿠폰 없음)")

                # 쿠폰 타입 필터가 있으면 해당 타입만 상세 출력
                if coupon_type_code:
                    self._print_coupon_type_details(
                        alias, rid, period["start"], period["end"], coupon_type_code
                    )

        self.stdout.write("\n" + "=" * 100 + "\n")

    def _get_default_periods(self, year, month):
        """기본 기간 설정 (12월 주차별)"""
        periods = []
        # 12월 1일부터 7일까지
        periods.append(
            {
                "name": "12.1 ~ 12.7",
                "start": datetime(year, month, 1).date(),
                "end": datetime(year, month, 7).date(),
            }
        )
        # 12월 8일부터 14일까지
        periods.append(
            {
                "name": "12.8 ~ 12.14",
                "start": datetime(year, month, 8).date(),
                "end": datetime(year, month, 14).date(),
            }
        )
        # 12월 15일부터 21일까지
        periods.append(
            {
                "name": "12.15 ~ 12.21",
                "start": datetime(year, month, 15).date(),
                "end": datetime(year, month, 21).date(),
            }
        )
        # 12월 22일부터 28일까지
        periods.append(
            {
                "name": "12.22 ~ 12.28",
                "start": datetime(year, month, 22).date(),
                "end": datetime(year, month, 28).date(),
            }
        )
        return periods

    def _get_event_campaigns(self, alias):
        """이벤트 Campaign 코드 목록 가져오기"""
        event_campaigns = Campaign.objects.using(alias).filter(
            Q(code__icontains="EVENT") | Q(code__icontains="FINAL_EXAM")
        ).values_list("code", flat=True)
        return list(event_campaigns)

    def _get_coupon_type_issued_count(
        self, alias, restaurant_id, start_date, end_date, coupon_type_codes
    ):
        """쿠폰 타입별 발급량 조회"""
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        count = (
            Coupon.objects.using(alias)
            .filter(
                restaurant_id=restaurant_id,
                coupon_type__code__in=coupon_type_codes,
                issued_at__gte=start_datetime,
                issued_at__lte=end_datetime,
            )
            .count()
        )
        return count

    def _get_coupon_type_usage_count(
        self, alias, restaurant_id, start_date, end_date, coupon_type_codes
    ):
        """쿠폰 타입별 사용량 조회"""
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        count = (
            Coupon.objects.using(alias)
            .filter(
                restaurant_id=restaurant_id,
                coupon_type__code__in=coupon_type_codes,
                status="REDEEMED",
                redeemed_at__gte=start_datetime,
                redeemed_at__lte=end_datetime,
            )
            .count()
        )
        return count

    def _get_event_issued_count(
        self, alias, restaurant_id, start_date, end_date, campaign_codes
    ):
        """이벤트 Campaign별 발급량 조회"""
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        issued_by_campaign = (
            Coupon.objects.using(alias)
            .filter(
                restaurant_id=restaurant_id,
                campaign__code__in=campaign_codes,
                issued_at__gte=start_datetime,
                issued_at__lte=end_datetime,
            )
            .values("campaign__code")
            .annotate(count=Count("id"))
        )

        return {item["campaign__code"]: item["count"] for item in issued_by_campaign}

    def _get_event_usage_count(
        self, alias, restaurant_id, start_date, end_date, campaign_codes
    ):
        """이벤트 Campaign별 사용량 조회"""
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        usage_by_campaign = (
            Coupon.objects.using(alias)
            .filter(
                restaurant_id=restaurant_id,
                campaign__code__in=campaign_codes,
                status="REDEEMED",
                redeemed_at__gte=start_datetime,
                redeemed_at__lte=end_datetime,
            )
            .values("campaign__code")
            .annotate(count=Count("id"))
        )

        return {item["campaign__code"]: item["count"] for item in usage_by_campaign}

    def _print_coupon_type_details(
        self, alias, restaurant_id, start_date, end_date, coupon_type_code
    ):
        """특정 쿠폰 타입의 상세 정보 출력"""
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, datetime.min.time())
        )
        end_datetime = timezone.make_aware(
            datetime.combine(end_date, datetime.max.time())
        )

        coupons = (
            Coupon.objects.using(alias)
            .filter(
                restaurant_id=restaurant_id,
                coupon_type__code=coupon_type_code,
                status="REDEEMED",
                redeemed_at__gte=start_datetime,
                redeemed_at__lte=end_datetime,
            )
            .select_related("coupon_type", "campaign", "user")
            .order_by("redeemed_at")
        )

        if coupons.exists():
            self.stdout.write(f"\n    상세 내역 ({coupon_type_code}):")
            for coupon in coupons[:10]:  # 최대 10개만 표시
                self.stdout.write(
                    f"      - 쿠폰 코드: {coupon.code}, "
                    f"사용일시: {coupon.redeemed_at.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"사용자 ID: {coupon.user.id}"
                )
            if coupons.count() > 10:
                self.stdout.write(f"      ... 외 {coupons.count() - 10}개 더 있습니다.")

