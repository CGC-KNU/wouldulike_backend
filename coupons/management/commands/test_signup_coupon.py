"""
신규가입 쿠폰 발급 테스트.
- 테스트용 User 생성
- issue_signup_coupon 호출
- 발급된 쿠폰 1개 및 대상 식당 출력
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, router

from coupons.models import Coupon, CouponType, Campaign
from coupons.service import issue_signup_coupon
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "신규가입 쿠폰 발급 테스트"

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao",
            type=int,
            help="테스트용 사용자 kakao_id. 미지정 시 랜덤 생성",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        kakao_id = options.get("kakao")

        if kakao_id:
            user = User.objects.filter(kakao_id=kakao_id).first()
            if not user:
                user = User.objects.create_user(kakao_id=kakao_id, type_code=None)
                self.stdout.write(f"사용자 생성: kakao_id={kakao_id}, user_id={user.id}")
        else:
            user = self._create_random_user(User)
            kakao_id = user.kakao_id

        self.stdout.write(
            self.style.SUCCESS(f"[1] 테스트 사용자: kakao_id={kakao_id}, user_id={user.id}")
        )

        try:
            coupons = issue_signup_coupon(user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[2] issue_signup_coupon 성공: 발급 쿠폰={len(coupons)}개"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[2] issue_signup_coupon 실패: {e}"))
            raise CommandError(str(e)) from e

        if coupons:
            alias = router.db_for_read(Coupon)
            ar_alias = router.db_for_read(AffiliateRestaurant)
            name_map = {
                r["restaurant_id"]: r["name"]
                for r in AffiliateRestaurant.objects.using(ar_alias).values(
                    "restaurant_id", "name"
                )
            }
            self.stdout.write("\n발급된 쿠폰:")
            for c in coupons:
                name = name_map.get(c.restaurant_id, "?")
                self.stdout.write(
                    f"  - {c.code}: restaurant_id={c.restaurant_id} ({name})"
                )
            c = coupons[0]
            snapshot = c.benefit_snapshot or {}
            self.stdout.write(f"\n  benefit_snapshot.subtitle: {snapshot.get('subtitle', '')}")
            self.stdout.write(f"  benefit_snapshot.title: {snapshot.get('title', '')}")
        else:
            self.stdout.write(self.style.WARNING("  발급된 쿠폰 없음 (이미 발급됨 또는 대상 없음)"))

        self.stdout.write(self.style.SUCCESS("\n✓ 신규가입 쿠폰 테스트 완료"))

    def _create_random_user(self, User):
        for _ in range(32):
            candidate = random.randint(910000000000, 999999999999)
            try:
                return User.objects.create_user(kakao_id=candidate, type_code=None)
            except IntegrityError:
                continue
        raise CommandError("사용 가능한 kakao_id를 찾지 못했습니다. --kakao 를 지정하세요.")
