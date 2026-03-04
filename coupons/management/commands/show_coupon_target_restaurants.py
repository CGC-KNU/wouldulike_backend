"""
쿠폰 발급 대상 식당 목록을 출력합니다.

1) CSV 기준: premium.csv + general.csv (NAME_TO_ID, EXCLUDE_NAMES)
   - 제휴식당 총 20개, 쿠폰 발급 16개 (4개 제외)
2) DB 기준: AffiliateRestaurant + RestaurantCouponBenefit + 제외 설정
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import router

from restaurants.models import AffiliateRestaurant
from coupons.models import CouponType, RestaurantCouponBenefit
from coupons.service import COUPON_TYPE_EXCLUDED_RESTAURANTS, _get_excluded_restaurant_ids

# import_affiliate_coupon_benefits_from_csv 와 동일
NAME_TO_ID = {
    "정든밤": 97,
    "구구포차": 33,
    "통통주먹구이": 145,
    "포차1번지먹새통": 147,
    "스톡홀름샐러드": 143,
    "스톡홀롬샐러드": 143,
    "벨로": 19,
    "닭동가리": 146,
    "마름모식당": 62,
    "주비두루": 144,
    "주비 두루": 144,
    "Better": 148,
    "북성로우동불고기": 266,
    "북성로 우동 불고기": 266,
    "난탄": 285,
    "사랑과평화": 271,
    "와비사비": 284,
    "한끼갈비": 74,
    "고니식탁": 30,
    "대부": 47,
    "대부 대왕유부초밥": 47,
    "부리또익스프레스": 41,
    "다이와스시": 56,
    "고씨네": 249,
}
EXCLUDE_NAMES = {"Better", "와비사비", "포차1번지먹새통", "고니식탁"}

# ID -> 대표 식당명 (첫 매칭)
ID_TO_NAME = {}
for name, rid in NAME_TO_ID.items():
    if rid not in ID_TO_NAME:
        ID_TO_NAME[rid] = name

COUPON_TYPES_TO_SHOW = [
    "WELCOME_3000",
    "REFERRAL_BONUS_REFERRER",
    "REFERRAL_BONUS_REFEREE",
    "FINAL_EXAM_SPECIAL",
    "NEW_SEMESTER_SPECIAL",
]


def _get_csv_based_lists():
    """CSV 기준 제휴 18개 (Better·와비사비 제외), 쿠폰 발급 16개 (고니·포차 제외) 반환."""
    all_ids = sorted(set(NAME_TO_ID.values()))
    # Better(148), 와비사비(284) = 제휴 아님
    non_affiliate = {148, 284}
    affiliate_ids = [rid for rid in all_ids if rid not in non_affiliate]  # 18개
    # 고니식탁(30), 포차1번지먹새통(147) = 쿠폰 발급 제외
    coupon_excluded = {30, 147}
    coupon_ids = [rid for rid in affiliate_ids if rid not in coupon_excluded]  # 16개
    return affiliate_ids, non_affiliate | coupon_excluded, coupon_ids


class Command(BaseCommand):
    help = "쿠폰 발급 대상 식당 목록 출력 (CSV 기준 + DB 기준)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-only",
            action="store_true",
            help="CSV 기준만 출력",
        )

    def handle(self, *args, **options):
        csv_only = options["csv_only"]

        # ---- CSV 기준 ----
        affiliate_csv, excluded_csv, coupon_csv = _get_csv_based_lists()
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("【CSV 기준】 premium.csv + general.csv (제휴 18개, 쿠폰 16개)")
        self.stdout.write("=" * 60)
        self.stdout.write(f"\n제휴식당 총 {len(affiliate_csv)}개 (Better·와비사비 제외):")
        for rid in affiliate_csv:
            name = ID_TO_NAME.get(rid, "?")
            ex = " (쿠폰 제외)" if rid in {30, 147} else ""
            self.stdout.write(f"  {rid}: {name}{ex}")

        self.stdout.write(f"\n쿠폰 발급 대상 {len(coupon_csv)}개 (고니식탁·포차1번지 제외):")
        for rid in coupon_csv:
            name = ID_TO_NAME.get(rid, "?")
            self.stdout.write(f"  {rid}: {name}")

        if csv_only:
            self.stdout.write("")
            return

        # ---- DB 기준 ----
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("【DB 기준】 AffiliateRestaurant + RestaurantCouponBenefit")
        self.stdout.write("=" * 60)

        alias = router.db_for_read(AffiliateRestaurant)
        benefit_alias = router.db_for_read(RestaurantCouponBenefit)

        all_affiliate_ids = list(
            AffiliateRestaurant.objects.using(alias)
            .filter(is_affiliate=True)
            .values_list("restaurant_id", flat=True)
        )
        all_affiliate_ids.sort()

        name_map = {}
        for r in AffiliateRestaurant.objects.using(alias).filter(
            restaurant_id__in=all_affiliate_ids
        ).values("restaurant_id", "name"):
            name_map[r["restaurant_id"]] = r["name"]

        self.stdout.write(f"\n제휴 식당 (is_affiliate=True): {len(all_affiliate_ids)}개")
        for rid in all_affiliate_ids:
            self.stdout.write(f"  {rid}: {name_map.get(rid, '?')}")

        # CSV에 있지만 DB에 없는 식당
        in_csv_not_db = set(affiliate_csv) - set(all_affiliate_ids)
        in_db_not_csv = set(all_affiliate_ids) - set(affiliate_csv)
        if in_csv_not_db:
            self.stdout.write(
                self.style.WARNING(f"\n⚠ CSV에 있으나 DB is_affiliate 없음: {sorted(in_csv_not_db)}")
            )
        if in_db_not_csv:
            self.stdout.write(
                self.style.WARNING(f"\n⚠ DB에 있으나 CSV NAME_TO_ID 없음: {sorted(in_db_not_csv)}")
            )

        for ct_code in COUPON_TYPES_TO_SHOW:
            try:
                ct = CouponType.objects.get(code=ct_code)
            except CouponType.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"\n[건너뜀] CouponType {ct_code} 없음"))
                continue

            excluded = _get_excluded_restaurant_ids(ct_code)
            hardcoded = COUPON_TYPE_EXCLUDED_RESTAURANTS.get(ct_code, set())

            target_ids = [rid for rid in all_affiliate_ids if rid not in excluded]

            benefit_restaurant_ids = set(
                RestaurantCouponBenefit.objects.using(benefit_alias)
                .filter(coupon_type=ct, restaurant_id__in=target_ids, active=True)
                .values_list("restaurant_id", flat=True)
                .distinct()
            )
            final_target = sorted(rid for rid in target_ids if rid in benefit_restaurant_ids)

            self.stdout.write(f"\n--- {ct_code} ---")
            self.stdout.write(f"  제외 (하드코딩): {sorted(hardcoded)}")
            self.stdout.write(f"  제외 (전체): {sorted(excluded)}")
            self.stdout.write(f"  발급 대상 (benefit 있음): {len(final_target)}개")
            for rid in final_target:
                self.stdout.write(f"    {rid}: {name_map.get(rid, '?')}")

            # CSV 16개 vs DB 비교
            missing = set(coupon_csv) - set(final_target)
            extra = set(final_target) - set(coupon_csv)
            if ct_code in ("WELCOME_3000", "REFERRAL_BONUS_REFERRER", "REFERRAL_BONUS_REFEREE"):
                if missing:
                    self.stdout.write(
                        self.style.WARNING(f"  → CSV 16개 대비 부족: {sorted(missing)}")
                    )
                if extra:
                    self.stdout.write(
                        self.style.WARNING(f"  → CSV 16개 대비 추가: {sorted(extra)}")
                    )

        self.stdout.write("")
