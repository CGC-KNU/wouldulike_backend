"""
핵밥 쿠폰(4종 benefit)을 전체 사용자에게 일괄 발급합니다.

특징:
- restaurant_id는 (옵션) 직접 지정하거나, cloudsql의 restaurants_affiliate에서 '핵밥'으로 검색해 자동 탐색합니다.
- benefit 4종은 RestaurantCouponBenefit(WELCOME_3000, restaurant_id, sort_order=0..N) 기준으로 발급합니다.
- 중복 발급 방지: (user, coupon_type, campaign, issue_key) 유니크 제약을 활용 (멱등).

사용 예:
  python manage.py issue_hackbob_coupons_to_all_users --dry-run
  python manage.py issue_hackbob_coupons_to_all_users --no-input
  python manage.py issue_hackbob_coupons_to_all_users --limit 100 --no-input
  python manage.py issue_hackbob_coupons_to_all_users --restaurant-id 123 --no-input
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, router, transaction
from django.utils import timezone

from coupons.models import Campaign, Coupon, CouponType, RestaurantCouponBenefit
from coupons.service import (
    _build_benefit_snapshot,
    _resolve_expires_at_for_issue,
)
from coupons.utils import make_coupon_code
from restaurants.models import AffiliateRestaurant


User = get_user_model()

DEFAULT_COUPON_TYPE_CODE = "WELCOME_3000"
DEFAULT_CAMPAIGN_CODE = "HACKBOB_ALL_USERS"
DEFAULT_CAMPAIGN_NAME = "Hackbob – All Users"
DEFAULT_ISSUE_SUBTITLE = "[신규 매장추가 쿠폰]"

HACKBOB_NAME_KEYWORD = "핵밥"
HACKBOB_ADDRESS_KEYWORD = "대구 북구 대학로 79"


def _find_hackbob_restaurant_id() -> int | None:
    """
    cloudsql에서 핵밥 restaurant_id 탐색.
    - 주소 키워드가 매칭되면 우선 선택.
    """
    try:
        qs = AffiliateRestaurant.objects.using("cloudsql").filter(
            name__icontains=HACKBOB_NAME_KEYWORD
        )
        rows = list(qs.values("restaurant_id", "address")[:20])
    except Exception:
        rows = []

    if not rows:
        # cloudsql이 없는 로컬 환경 등에선 default도 시도
        rows = list(
            AffiliateRestaurant.objects.filter(name__icontains=HACKBOB_NAME_KEYWORD).values(
                "restaurant_id", "address"
            )[:20]
        )

    if not rows:
        return None

    for r in rows:
        addr = (r.get("address") or "").strip()
        if HACKBOB_ADDRESS_KEYWORD in addr:
            return int(r["restaurant_id"])

    return int(rows[0]["restaurant_id"])


class Command(BaseCommand):
    help = "핵밥 쿠폰 4종을 전체 사용자에게 일괄 발급합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            default=None,
            help="핵밥 restaurant_id (미지정 시 cloudsql에서 '핵밥'으로 자동 탐색)",
        )
        parser.add_argument(
            "--coupon-type-code",
            type=str,
            default=DEFAULT_COUPON_TYPE_CODE,
            help=f"발급할 쿠폰 타입 코드 (기본: {DEFAULT_COUPON_TYPE_CODE})",
        )
        parser.add_argument(
            "--campaign-code",
            type=str,
            default=DEFAULT_CAMPAIGN_CODE,
            help=f"발급 캠페인 코드 (기본: {DEFAULT_CAMPAIGN_CODE})",
        )
        parser.add_argument(
            "--campaign-name",
            type=str,
            default=DEFAULT_CAMPAIGN_NAME,
            help=f"발급 캠페인 이름 (기본: {DEFAULT_CAMPAIGN_NAME})",
        )
        parser.add_argument(
            "--subtitle",
            type=str,
            default=DEFAULT_ISSUE_SUBTITLE,
            help="발급되는 쿠폰 benefit_snapshot.subtitle에 강제 반영할 문구 (기본: '핵밥')",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 발급하지 않고 대상/개수만 출력",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 프롬프트 없이 바로 실행",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="최대 N명만 처리 (테스트용)",
        )

    def handle(self, *args, **options):
        restaurant_id: int | None = options.get("restaurant_id")
        coupon_type_code: str = options["coupon_type_code"]
        campaign_code: str = options["campaign_code"]
        campaign_name: str = options["campaign_name"]
        subtitle: str = options["subtitle"]
        dry_run: bool = options["dry_run"]
        no_input: bool = options["no_input"]
        limit: int | None = options.get("limit")

        if restaurant_id is None:
            restaurant_id = _find_hackbob_restaurant_id()
        if not restaurant_id:
            raise CommandError(
                "핵밥 restaurant_id를 찾지 못했습니다. --restaurant-id로 직접 지정해주세요."
            )

        coupon_alias = router.db_for_write(Coupon)
        benefit_alias = router.db_for_read(RestaurantCouponBenefit)

        try:
            ct = CouponType.objects.using(coupon_alias).get(code=coupon_type_code)
        except CouponType.DoesNotExist:
            raise CommandError(f"CouponType(code='{coupon_type_code}') 를 찾을 수 없습니다.")

        # 핵밥 benefit 4종(여러 줄) 가져오기
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
            .order_by("sort_order", "id")
        )
        if not benefits:
            raise CommandError(
                f"restaurant_id={restaurant_id}에 대해 {coupon_type_code} benefit이 없습니다. "
                "먼저 RestaurantCouponBenefit(4종)이 들어있는지 확인해주세요."
            )

        self.stdout.write(
            f"\n대상 식당: restaurant_id={restaurant_id} / coupon_type={coupon_type_code}"
        )
        self.stdout.write(f"benefit 수: {len(benefits)}개 (sort_order 기준)")
        for b in benefits[:10]:
            self.stdout.write(f"  - sort={b.sort_order} title={b.title}")

        # 캠페인 upsert (멱등)
        camp, _ = Campaign.objects.using(coupon_alias).update_or_create(
            code=campaign_code,
            defaults={
                "name": campaign_name,
                "type": "SIGNUP",
                "active": True,
                "rules_json": {},
            },
        )

        # 사용자 목록
        user_qs = User.objects.using(router.db_for_read(User)).order_by("id")
        if limit:
            user_qs = user_qs[:limit]
        user_ids = list(user_qs.values_list("id", flat=True))
        if not user_ids:
            self.stdout.write(self.style.SUCCESS("대상 사용자가 없습니다."))
            return

        self.stdout.write(f"\n대상 사용자 수: {len(user_ids)}명")
        self.stdout.write(f"캠페인: {campaign_code} / subtitle='{subtitle}'")

        planned = len(user_ids) * len(benefits)
        self.stdout.write(f"발급 예정 쿠폰 수(최대): {planned}개")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제 발급 없이 종료합니다."))
            return

        if not no_input:
            confirm = input(
                f"\n위 {len(user_ids)}명에게 핵밥 쿠폰 {len(benefits)}종씩 발급합니다. 계속할까요? (yes/no): "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소되었습니다.")
                return

        success = 0
        skipped = 0
        failed = 0

        expires_at = _resolve_expires_at_for_issue(ct, campaign=camp)
        issued_at = timezone.now()

        with transaction.atomic(using=coupon_alias):
            for uid in user_ids:
                try:
                    user = User.objects.using(router.db_for_read(User)).get(id=uid)
                except User.DoesNotExist:
                    failed += 1
                    continue

                for benefit in benefits:
                    sort_key = getattr(benefit, "sort_order", 0)
                    issue_key = f"{campaign_code}:{uid}:{restaurant_id}:{coupon_type_code}:{sort_key}"

                    exists = (
                        Coupon.objects.using(coupon_alias)
                        .filter(
                            user_id=uid,
                            coupon_type=ct,
                            campaign=camp,
                            issue_key=issue_key,
                        )
                        .exists()
                    )
                    if exists:
                        skipped += 1
                        continue

                    benefit_snapshot = _build_benefit_snapshot(
                        ct,
                        restaurant_id,
                        benefit=benefit,
                        db_alias=coupon_alias,
                    )
                    benefit_snapshot["subtitle"] = subtitle
                    benefit_snapshot["issue_type_label"] = "일괄 발급"

                    try:
                        Coupon.objects.using(coupon_alias).create(
                            code=make_coupon_code(),
                            user=user,
                            coupon_type=ct,
                            campaign=camp,
                            restaurant_id=restaurant_id,
                            issued_at=issued_at,
                            expires_at=expires_at,
                            issue_key=issue_key,
                            benefit_snapshot=benefit_snapshot,
                        )
                        success += 1
                    except IntegrityError:
                        skipped += 1
                    except Exception:
                        failed += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 발급 {success}개, 스킵(중복) {skipped}개, 실패 {failed}개"
            )
        )

