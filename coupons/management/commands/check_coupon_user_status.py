"""
전체 사용자 중 다음 두 가지를 점검합니다:
1) 제휴식당이 아닌 곳(is_affiliate=False 또는 AffiliateRestaurant에 없음)에 쿠폰이 발급된 사용자
2) 쿠폰함이 비어 있는 사용자

사용 예:
  python manage.py check_coupon_user_status
  python manage.py check_coupon_user_status --limit 50
"""
from django.core.management.base import BaseCommand
from django.db import router
from django.contrib.auth import get_user_model

from restaurants.models import AffiliateRestaurant
from coupons.models import Coupon

User = get_user_model()


class Command(BaseCommand):
    help = (
        "전체 사용자 점검: "
        "1) 제휴 해제 식당 쿠폰 보유 사용자, 2) 쿠폰함 비어 있는 사용자"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            metavar="N",
            help="출력 시 샘플 개수 제한 (기본: 20)",
            default=20,
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        coupon_alias = router.db_for_read(Coupon)
        ar_alias = router.db_for_read(AffiliateRestaurant)

        # 1) 현재 제휴 식당 ID (is_affiliate=True)
        affiliate_ids = set(
            AffiliateRestaurant.objects.using(ar_alias)
            .filter(is_affiliate=True)
            .values_list("restaurant_id", flat=True)
        )
        self.stdout.write(f"\n현재 제휴 식당 (is_affiliate=True): {len(affiliate_ids)}개")

        # 2) 제휴 해제 또는 AffiliateRestaurant에 없는 식당에 발급된 쿠폰
        # restaurant_id가 NULL이 아닌 쿠폰 중, affiliate_ids에 없는 것
        all_coupons_with_restaurant = list(
            Coupon.objects.using(coupon_alias)
            .exclude(restaurant_id__isnull=True)
            .values_list("id", "user_id", "restaurant_id", "status", "issue_key")
        )

        non_affiliate_coupons = [
            c for c in all_coupons_with_restaurant if c[2] not in affiliate_ids
        ]

        # 제휴 해제 식당 ID 목록 (AffiliateRestaurant에 있으나 is_affiliate=False)
        unaffiliated_in_db = set(
            AffiliateRestaurant.objects.using(ar_alias)
            .filter(is_affiliate=False)
            .values_list("restaurant_id", flat=True)
        )
        # AffiliateRestaurant에 아예 없는 식당 (삭제됐거나 미등록)
        all_restaurant_ids_in_coupons = {c[2] for c in non_affiliate_coupons}
        not_in_affiliate_table = all_restaurant_ids_in_coupons - unaffiliated_in_db

        users_with_non_affiliate_coupons = sorted(
            set(c[1] for c in non_affiliate_coupons)
        )

        # 3) 쿠폰함이 비어 있는 사용자
        users_with_coupons = set(
            Coupon.objects.using(coupon_alias)
            .values_list("user_id", flat=True)
            .distinct()
        )
        total_users = User.objects.count()
        users_with_empty_wallet = total_users - len(users_with_coupons)

        # 쿠폰 없는 사용자 ID (샘플용)
        users_without_coupons = list(
            User.objects.exclude(id__in=users_with_coupons)
            .order_by("id")
            .values_list("id", "kakao_id", "created_at")[:limit]
        )

        # === 출력 ===
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("【1】 제휴식당이 아닌 곳에 쿠폰이 발급된 사용자")
        self.stdout.write("=" * 70)

        if not non_affiliate_coupons:
            self.stdout.write(self.style.SUCCESS("  해당 없음 (모든 쿠폰이 제휴 식당에 발급됨)"))
        else:
            self.stdout.write(f"  쿠폰 수: {len(non_affiliate_coupons)}개")
            self.stdout.write(f"  해당 사용자 수: {len(users_with_non_affiliate_coupons)}명")

            # restaurant_id별 분포 + 식당명
            from collections import Counter
            rid_counts = Counter(c[2] for c in non_affiliate_coupons)
            rid_to_name = {
                r.restaurant_id: r.name
                for r in AffiliateRestaurant.objects.using(ar_alias).filter(
                    restaurant_id__in=rid_counts.keys()
                ).values("restaurant_id", "name")
            }
            self.stdout.write("\n  [식당별 쿠폰 수]")
            for rid, cnt in rid_counts.most_common(15):
                name = rid_to_name.get(rid, "?")
                in_db = "DB에 있음(is_affiliate=False)" if rid in unaffiliated_in_db else "AffiliateRestaurant에 없음"
                self.stdout.write(f"    restaurant_id={rid} ({name}): {cnt}개 ({in_db})")
            if len(rid_counts) > 15:
                self.stdout.write(f"    ... 외 {len(rid_counts) - 15}개 식당")

            self.stdout.write(f"\n  [사용자 샘플 (최대 {limit}명)]")
            for c in non_affiliate_coupons[:limit]:
                uid, rid, status, issue_key = c[1], c[2], c[3], (c[4] or "")[:30]
                self.stdout.write(f"    user_id={uid}, restaurant_id={rid}, status={status}, issue_key={issue_key}...")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("【2】 쿠폰함이 비어 있는 사용자")
        self.stdout.write("=" * 70)

        self.stdout.write(f"  전체 사용자: {total_users}명")
        self.stdout.write(f"  쿠폰 보유 사용자: {len(users_with_coupons)}명")
        self.stdout.write(f"  쿠폰함 비어 있음: {users_with_empty_wallet}명")

        if users_without_coupons:
            self.stdout.write(f"\n  [샘플 (최대 {limit}명)]")
            for uid, kid, created in users_without_coupons:
                kid_str = str(kid) if kid else "-"
                self.stdout.write(f"    user_id={uid}, kakao_id={kid_str}, 가입일={created}")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("점검 완료")
        self.stdout.write("=" * 70 + "\n")
