"""
환경변수에 따른 앱 접속 쿠폰 발급 동작 테스트.

시나리오:
1. 환경변수 미등록 (LEGACY=1, MON_WED=0 기본값): LEGACY만 실행
2. 환경변수 등록 (LEGACY=0, MON_WED=1): MON_WED만 실행, 월/수 각각 1장
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from coupons.models import Coupon
from coupons.service import (
    issue_app_open_coupon,
    APP_OPEN_LEGACY_ENABLED,
    APP_OPEN_MON_WED_ENABLED,
)


class Command(BaseCommand):
    help = "환경변수별 앱 접속 쿠폰 발급 동작 테스트"

    def handle(self, *args, **options):
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("사용자 없음"))
            return

        self.stdout.write("=" * 60)
        self.stdout.write("현재 환경변수 값 (프로세스 로드 시점)")
        self.stdout.write("=" * 60)
        self.stdout.write(f"  APP_OPEN_LEGACY_ENABLED: {APP_OPEN_LEGACY_ENABLED}")
        self.stdout.write(f"  APP_OPEN_MON_WED_ENABLED: {APP_OPEN_MON_WED_ENABLED}")
        self.stdout.write("")

        # 오늘 요일
        kst = timezone.now().astimezone(ZoneInfo("Asia/Seoul"))
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        self.stdout.write(f"현재(한국): {kst.strftime('%Y-%m-%d')} {weekday_names[kst.weekday()]}요일")
        self.stdout.write("")

        # 기존 앱접속 쿠폰 수
        before_mon = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_MON").count()
        before_wed = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_WED").count()
        before_legacy = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_3000").count()
        self.stdout.write("발급 전 쿠폰 수:")
        self.stdout.write(f"  APP_OPEN_MON: {before_mon}, APP_OPEN_WED: {before_wed}, APP_OPEN_3000: {before_legacy}")
        self.stdout.write("")

        # 발급 시도
        self.stdout.write("issue_app_open_coupon(user) 호출...")
        issued = issue_app_open_coupon(user)
        self.stdout.write(f"  반환: {len(issued)}장")
        if issued:
            for c in issued:
                self.stdout.write(f"    - {c.coupon_type.code} (restaurant_id={c.restaurant_id})")
        self.stdout.write("")

        # 발급 후
        after_mon = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_MON").count()
        after_wed = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_WED").count()
        after_legacy = Coupon.objects.filter(user=user, coupon_type__code="APP_OPEN_3000").count()
        self.stdout.write("발급 후 쿠폰 수:")
        self.stdout.write(f"  APP_OPEN_MON: {after_mon}, APP_OPEN_WED: {after_wed}, APP_OPEN_3000: {after_legacy}")
        self.stdout.write("")

        # 월/수 시뮬레이션
        self.stdout.write("=" * 60)
        self.stdout.write("월/수 시뮬레이션 (MON_WED_ENABLED=1 일 때만 해당)")
        self.stdout.write("=" * 60)
        for day_name, mock_dt in [
            ("월요일", datetime(2026, 3, 16, 1, 0, 0, tzinfo=ZoneInfo("UTC"))),
            ("수요일", datetime(2026, 3, 18, 1, 0, 0, tzinfo=ZoneInfo("UTC"))),
            ("목요일", datetime(2026, 3, 19, 1, 0, 0, tzinfo=ZoneInfo("UTC"))),
        ]:
            with patch("coupons.service.timezone.now", return_value=mock_dt):
                # 재호출 시 기존 쿠폰 반환 (이미 있으면 새로 발급 안 함)
                sim_issued = issue_app_open_coupon(user)
                new_count = sum(1 for c in sim_issued if c.coupon_type.code in ("APP_OPEN_MON", "APP_OPEN_WED"))
                self.stdout.write(f"  {day_name}: {'1장 반환' if sim_issued else '0장'} (신규 {new_count})")
