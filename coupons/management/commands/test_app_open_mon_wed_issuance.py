"""
월/수 앱 접속 쿠폰 발급 테스트.
--simulate-mon 또는 --simulate-wed 로 해당 요일로 시뮬레이션하여 발급을 시도합니다.
--debug: 단계별 디버그 출력
"""
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone as tz
from django.db import router

from accounts.models import User
from coupons.models import CouponType, Campaign, RestaurantCouponBenefit, Coupon
from restaurants.models import AffiliateRestaurant
from coupons.service import (
    _issue_app_open_mon_wed,
    _get_non_pub_restaurant_ids,
    _get_pub_restaurant_ids,
    _select_single_restaurant_from_pool,
    _build_benefit_snapshot,
    _expires_at,
    make_coupon_code,
)


class Command(BaseCommand):
    help = "월/수 앱 접속 쿠폰 발급 테스트 (--simulate-mon/--simulate-wed)"

    def add_arguments(self, parser):
        parser.add_argument("--simulate-mon", action="store_true", help="월요일로 시뮬레이션")
        parser.add_argument("--simulate-wed", action="store_true", help="수요일로 시뮬레이션")
        parser.add_argument("--user-id", type=int, help="테스트할 사용자 ID (기본: 첫 번째)")
        parser.add_argument("--debug", action="store_true", help="단계별 디버그 출력")

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        user = User.objects.filter(pk=user_id).first() if user_id else User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("사용자를 찾을 수 없습니다."))
            return

        if options.get("simulate_mon"):
            # 2026-03-16 월 10:00 KST = 01:00 UTC
            mock_now = datetime(2026, 3, 16, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
            day_label = "월요일"
        elif options.get("simulate_wed"):
            # 2026-03-18 수 10:00 KST = 01:00 UTC
            mock_now = datetime(2026, 3, 18, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
            day_label = "수요일"
        else:
            self.stdout.write("--simulate-mon 또는 --simulate-wed 를 지정하세요.")
            return

        self.stdout.write(f"시뮬레이션: {day_label} (user_id={user.id})")

        # coupons.service에서 사용하는 timezone.now 패치
        with patch("coupons.service.timezone.now", return_value=mock_now):
            issued = _issue_app_open_mon_wed(user)

        if issued:
            c = issued[0]
            self.stdout.write(self.style.SUCCESS(f"발급 성공: {len(issued)}장"))
            self.stdout.write(f"  code: {c.code}")
            self.stdout.write(f"  coupon_type: {c.coupon_type.code}")
            self.stdout.write(f"  restaurant_id: {c.restaurant_id}")
            self.stdout.write(f"  expires_at: {c.expires_at}")
            if c.benefit_snapshot:
                self.stdout.write(f"  식당: {c.benefit_snapshot.get('restaurant_name', '-')}")
        else:
            self.stdout.write(self.style.WARNING("발급된 쿠폰 없음"))
            if options.get("debug"):
                self._run_debug(user, mock_now, day_label, options)

    def _run_debug(self, user, mock_now, day_label, options):
        """단계별 디버그 출력"""
        alias = router.db_for_write(Coupon)
        kst = mock_now.astimezone(ZoneInfo("Asia/Seoul"))
        weekday = kst.weekday()
        self.stdout.write(f"\n[DEBUG] kst={kst}, weekday={weekday} (0=월,2=수)")

        if weekday == 0:
            ct_code, camp_code = "APP_OPEN_MON", "APP_OPEN_MON_EVENT"
            is_pub_filter = False
        else:
            ct_code, camp_code = "APP_OPEN_WED", "APP_OPEN_WED_EVENT"
            is_pub_filter = True

        try:
            ct = CouponType.objects.using(alias).get(code=ct_code)
            camp = Campaign.objects.using(alias).get(code=camp_code, active=True)
            self.stdout.write(f"[DEBUG] ct={ct.code}, camp={camp.code} OK")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[DEBUG] ct/camp 조회 실패: {e}"))
            return

        all_ids = list(
            AffiliateRestaurant.objects.using(alias)
            .filter(is_affiliate=True)
            .values_list("restaurant_id", flat=True)
        )
        pool_ids = _get_pub_restaurant_ids(all_ids, db_alias=alias) if is_pub_filter else _get_non_pub_restaurant_ids(all_ids, db_alias=alias)
        self.stdout.write(f"[DEBUG] 제휴={len(all_ids)}개, pool={len(pool_ids)}개")

        restaurant_id = _select_single_restaurant_from_pool(ct, pool_ids, db_alias=alias)
        self.stdout.write(f"[DEBUG] 선정 restaurant_id: {restaurant_id}")

        if restaurant_id:
            benefit = (
                RestaurantCouponBenefit.objects.using(alias)
                .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
                .order_by("sort_order")
                .first()
            )
            self.stdout.write(f"[DEBUG] benefit: {benefit}")
