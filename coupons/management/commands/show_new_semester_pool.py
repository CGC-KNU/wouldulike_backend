"""
NEW_SEMESTER_SPECIAL 쿠폰 발급 풀(대상 benefit 목록)을 출력합니다.
newsemeseter 코드 입력 시 이 풀 중 3개가 랜덤 발급됩니다.
Cloud DB 연결 필요.
"""
from django.core.management.base import BaseCommand
from django.db import router

from coupons.models import CouponType, RestaurantCouponBenefit
from coupons.service import COUPON_TYPE_EXCLUDED_RESTAURANTS, _get_excluded_restaurant_ids
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "NEW_SEMESTER_SPECIAL 쿠폰 발급 풀(대상 benefit) 확인"

    def handle(self, *args, **options):
        try:
            ct = CouponType.objects.get(code="NEW_SEMESTER_SPECIAL")
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("NEW_SEMESTER_SPECIAL CouponType이 없습니다. 마이그레이션 0028, 0029를 실행하세요."))
            return

        excluded = _get_excluded_restaurant_ids("NEW_SEMESTER_SPECIAL")
        hardcoded = COUPON_TYPE_EXCLUDED_RESTAURANTS.get("NEW_SEMESTER_SPECIAL", set())

        alias = router.db_for_read(RestaurantCouponBenefit)
        ar_alias = router.db_for_read(AffiliateRestaurant)
        name_map = {
            r["restaurant_id"]: r["name"]
            for r in AffiliateRestaurant.objects.using(ar_alias).values("restaurant_id", "name")
        }

        benefits = list(
            RestaurantCouponBenefit.objects.using(alias)
            .filter(coupon_type=ct, active=True)
            .exclude(restaurant_id__in=excluded)
            .order_by("restaurant_id", "sort_order")
            .values("restaurant_id", "sort_order", "title")
        )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("NEW_SEMESTER_SPECIAL 쿠폰 발급 풀")
        self.stdout.write("=" * 60)
        self.stdout.write(f"제외 식당 (하드코딩): {sorted(hardcoded)}")
        self.stdout.write(f"제외 식당 (전체): {sorted(excluded)}")
        self.stdout.write(f"\n발급 풀 크기: {len(benefits)}개 (이 중 3개 랜덤 발급)")
        self.stdout.write("\n대상 benefit 목록:")
        for b in benefits:
            name = name_map.get(b["restaurant_id"], "?")
            self.stdout.write(f"  restaurant_id={b['restaurant_id']} ({name}), sort_order={b['sort_order']}: {b['title'][:40]}...")
        self.stdout.write("")
