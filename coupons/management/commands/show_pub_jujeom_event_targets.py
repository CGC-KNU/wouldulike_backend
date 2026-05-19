"""주점·술집 이벤트 쿠폰(PUB_JUJEOM_EVENT) 발급 대상 식당 목록."""
from django.core.management.base import BaseCommand
from django.db import router

from coupons.models import CouponType, RestaurantCouponBenefit
from coupons.service import (
    AFFILIATE_CATEGORY_JUJEOM,
    PUB_JUJEOM_EVENT_COUPON_TYPE_CODE,
    _get_excluded_restaurant_ids,
    _get_jujeom_restaurant_ids,
    _is_pub_restaurant,
)
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "술집·주점 제휴 식당 중 PUB_JUJEOM_EVENT benefit 이 있는 발급 대상 출력"

    def handle(self, *args, **options):
        alias = router.db_for_read(AffiliateRestaurant)
        coupon_alias = router.db_for_read(CouponType)
        target_ids = sorted(_get_jujeom_restaurant_ids(db_alias=alias))
        name_map = {
            r["restaurant_id"]: r
            for r in AffiliateRestaurant.objects.using(alias)
            .filter(restaurant_id__in=target_ids)
            .values("restaurant_id", "name", "category", "pub_option")
        }

        jujeom_only = []
        pub_only = []
        both = []
        for rid in target_ids:
            row = name_map.get(rid) or {}
            cat = (row.get("category") or "").strip()
            is_jujeom = cat == AFFILIATE_CATEGORY_JUJEOM
            is_pub = _is_pub_restaurant(rid, db_alias=alias)
            if is_jujeom and is_pub:
                both.append(rid)
            elif is_jujeom:
                jujeom_only.append(rid)
            else:
                pub_only.append(rid)

        self.stdout.write(
            "\n【선정 기준】 is_affiliate=True 이고 아래 중 하나 이상\n"
            f"  - category='{AFFILIATE_CATEGORY_JUJEOM}'\n"
            "  - 수요일 술집: pub_option='네'(또는 '네,' 시작) 또는 category='술집'\n"
        )
        self.stdout.write(f"합집합 대상: {len(target_ids)}개")
        self.stdout.write(f"  주점만: {len(jujeom_only)} / 술집만: {len(pub_only)} / 둘 다: {len(both)}\n")
        for rid in target_ids:
            row = name_map.get(rid) or {}
            self.stdout.write(
                f"  {rid}: {row.get('name', '?')} "
                f"(category={row.get('category') or '-'}, pub_option={row.get('pub_option') or '-'})"
            )

        self.stdout.write(f"\n쿠폰 DB alias: {coupon_alias!r} (제휴식당: {alias!r})\n")

        try:
            ct = CouponType.objects.using(coupon_alias).get(
                code=PUB_JUJEOM_EVENT_COUPON_TYPE_CODE
            )
        except CouponType.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    "\nCouponType PUB_JUJEOM_EVENT 없음 — 아래 중 하나 실행:\n"
                    "  python manage.py migrate coupons 0066\n"
                    "  python manage.py ensure_pub_jujeom_event\n"
                )
            )
            return

        excluded = _get_excluded_restaurant_ids(ct.code, db_alias=coupon_alias)
        benefit_ids = sorted(
            RestaurantCouponBenefit.objects.using(coupon_alias).filter(
                coupon_type=ct,
                active=True,
                restaurant_id__in=target_ids,
            )
            .exclude(restaurant_id__in=excluded)
            .values_list("restaurant_id", flat=True)
            .distinct()
        )
        self.stdout.write(f"\n【실제 발급 풀】 benefit 활성 + 제외 아님: {len(benefit_ids)}개\n")
        for rid in benefit_ids:
            row = name_map.get(rid) or {}
            self.stdout.write(f"  {rid}: {row.get('name', '?')}")
        missing_benefits = sorted(set(target_ids) - set(benefit_ids) - excluded)
        if missing_benefits:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ 대상 식당 중 benefit 없음: {len(missing_benefits)}개 "
                    "(ensure_pub_jujeom_event 실행 필요)"
                )
            )
            for rid in missing_benefits:
                row = name_map.get(rid) or {}
                self.stdout.write(f"  {rid}: {row.get('name', '?')}")
        if len(benefit_ids) < 5:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ YUNJI(5종)는 풀 {len(benefit_ids)}개면 최대 {len(benefit_ids)}장만 발급됩니다."
                )
            )
        self.stdout.write("")
