"""
DONGARILIKE(제휴식당 전체) 및 KNULIKE 추천코드 입력 시 쿠폰 발급 테스트.
- DONGARILIKE: 제휴식당 21종 전체 발급
- KNULIKE: 제휴식당 쿠폰 3개 발급
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, router

from coupons.models import Coupon, CouponType, Campaign
from coupons.service import accept_referral, FULL_AFFILIATE_COUPON_CODE
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "DONGARILIKE 및 KNULIKE 추천코드 입력 시 쿠폰 발급 테스트"

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-full",
            type=int,
            help="DONGARILIKE 테스트용 피추천인 kakao_id. 미지정 시 랜덤 생성",
        )
        parser.add_argument(
            "--kakao-knulike",
            type=int,
            help="KNULIKE 테스트용 피추천인 kakao_id. 미지정 시 랜덤 생성",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("1. DONGARILIKE (제휴식당 전체) 쿠폰 테스트"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self._test_full_affiliate(User, options.get("kakao_full"))

        self.stdout.write("\n")
        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("2. KNULIKE 쿠폰 테스트"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self._test_knulike(User, options.get("kakao_knulike"))

        self.stdout.write(self.style.SUCCESS("\n✓ DONGARILIKE & KNULIKE 발급 테스트 완료"))

    def _create_random_user(self, User):
        for _ in range(32):
            candidate = random.randint(910000000000, 999999999999)
            try:
                return User.objects.create_user(kakao_id=candidate, type_code=None)
            except IntegrityError:
                continue
        raise CommandError("사용 가능한 kakao_id를 찾지 못했습니다. --kakao-full / --kakao-knulike 를 지정하세요.")

    def _test_full_affiliate(self, User, kakao_id):
        if kakao_id:
            referee = User.objects.filter(kakao_id=kakao_id).first()
            if not referee:
                referee = User.objects.create_user(kakao_id=kakao_id, type_code=None)
        else:
            referee = self._create_random_user(User)
            kakao_id = referee.kakao_id

        self.stdout.write(f"[1] 테스트 사용자: kakao_id={kakao_id}, user_id={referee.id}")

        code = FULL_AFFILIATE_COUPON_CODE
        try:
            referral, issued = accept_referral(referee=referee, ref_code=code)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[2] accept_referral({code}) 성공: referral_id={referral.id}, "
                    f"발급 쿠폰={len(issued)}개"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[2] accept_referral({code}) 실패: {e}"))
            raise CommandError(str(e)) from e

        self._print_issued_coupons(issued)

        self.stdout.write(f"\n[3] 중복 입력 시도 ({code})...")
        try:
            accept_referral(referee=referee, ref_code=code)
            self.stdout.write(self.style.WARNING("  → 중복 입력이 허용됨 (예상과 다름)"))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"  → 예상대로 거부됨: {e}"))

    def _test_knulike(self, User, kakao_id):
        if kakao_id:
            referee = User.objects.filter(kakao_id=kakao_id).first()
            if not referee:
                referee = User.objects.create_user(kakao_id=kakao_id, type_code=None)
        else:
            referee = self._create_random_user(User)
            kakao_id = referee.kakao_id

        self.stdout.write(f"[1] 테스트 사용자: kakao_id={kakao_id}, user_id={referee.id}")

        code = "KNULIKE"
        try:
            referral, issued = accept_referral(referee=referee, ref_code=code)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[2] accept_referral({code}) 성공: referral_id={referral.id}, "
                    f"발급 쿠폰={len(issued)}개"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[2] accept_referral({code}) 실패: {e}"))
            raise CommandError(str(e)) from e

        self._print_issued_coupons(issued)

        self.stdout.write(f"\n[3] 중복 입력 시도 ({code})...")
        try:
            accept_referral(referee=referee, ref_code=code)
            self.stdout.write(self.style.WARNING("  → 중복 입력이 허용됨 (예상과 다름)"))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"  → 예상대로 거부됨: {e}"))

    def _print_issued_coupons(self, issued):
        if not issued:
            return
        alias = router.db_for_read(Coupon)
        ar_alias = router.db_for_read(AffiliateRestaurant)
        name_map = {
            r["restaurant_id"]: r["name"]
            for r in AffiliateRestaurant.objects.using(ar_alias).values(
                "restaurant_id", "name"
            )
        }
        self.stdout.write("\n발급된 쿠폰:")
        for c in issued[:10]:
            name = name_map.get(c.restaurant_id, "?")
            self.stdout.write(f"  - {c.code}: restaurant_id={c.restaurant_id} ({name})")
        if len(issued) > 10:
            self.stdout.write(f"  ... 외 {len(issued) - 10}개")
