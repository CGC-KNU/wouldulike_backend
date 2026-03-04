"""
newsemeseter 추천코드 입력 시 쿠폰 3개 발급 테스트.
- 테스트용 User 생성
- accept_referral(ref_code="newsemeseter") 호출
- 발급된 쿠폰 수 및 대상 식당 출력
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, router

from coupons.models import Coupon, CouponType, Campaign
from coupons.service import accept_referral
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "newsemeseter 추천코드 입력 시 쿠폰 3개 발급 테스트"

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao",
            type=int,
            help="테스트용 피추천인 kakao_id. 미지정 시 랜덤 생성",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        kakao_id = options.get("kakao")

        if kakao_id:
            referee, _ = User.objects.get_or_create(
                kakao_id=kakao_id, defaults={"type_code": None}
            )
        else:
            referee = self._create_random_user(User)
            kakao_id = referee.kakao_id

        self.stdout.write(
            self.style.SUCCESS(f"[1] 테스트 사용자: kakao_id={kakao_id}, user_id={referee.id}")
        )

        # accept_referral with newsemeseter
        try:
            referral, issued = accept_referral(referee=referee, ref_code="newsemeseter")
            self.stdout.write(
                self.style.SUCCESS(
                    f"[2] accept_referral 성공: referral_id={referral.id}, "
                    f"발급 쿠폰={len(issued)}개"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[2] accept_referral 실패: {e}"))
            raise CommandError(str(e)) from e

        # 발급된 쿠폰 상세
        alias = router.db_for_read(Coupon)
        ar_alias = router.db_for_read(AffiliateRestaurant)
        name_map = {
            r["restaurant_id"]: r["name"]
            for r in AffiliateRestaurant.objects.using(ar_alias).values(
                "restaurant_id", "name"
            )
        }

        self.stdout.write("\n발급된 쿠폰:")
        for c in issued:
            name = name_map.get(c.restaurant_id, "?")
            self.stdout.write(f"  - {c.code}: restaurant_id={c.restaurant_id} ({name})")

        # 중복 입력 시도 (이미 발급받았으면 에러)
        self.stdout.write("\n[3] 중복 입력 시도 (이미 발급받았으면 에러 예상)...")
        try:
            accept_referral(referee=referee, ref_code="newsemeseter")
            self.stdout.write(self.style.WARNING("  → 중복 입력이 허용됨 (예상과 다름)"))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"  → 예상대로 거부됨: {e}"))

        self.stdout.write(self.style.SUCCESS("\n✓ newsemeseter 발급 테스트 완료"))

    def _create_random_user(self, User):
        for _ in range(32):
            candidate = random.randint(910000000000, 999999999999)
            try:
                return User.objects.create(kakao_id=candidate, type_code=None)
            except IntegrityError:
                continue
        raise CommandError("사용 가능한 kakao_id를 찾지 못했습니다. --kakao 를 지정하세요.")
