"""
추천코드 하나 생성 후 정상 발급되는지 테스트하는 management command.
- 추천인(User A) 생성 + InviteCode 발급
- 피추천인(User B) 생성
- accept_referral → qualify_referral_and_grant 호출
- 발급된 쿠폰 수 출력
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from coupons.service import accept_referral, ensure_invite_code, qualify_referral_and_grant


class Command(BaseCommand):
    help = "추천코드 생성 후 accept → qualify 흐름으로 정상 발급 테스트"

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-a",
            type=int,
            help="추천인(Referrer) kakao_id. 미지정 시 랜덤 생성",
        )
        parser.add_argument(
            "--kakao-b",
            type=int,
            help="피추천인(Referee) kakao_id. 미지정 시 랜덤 생성",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        kakao_a = options.get("kakao_a")
        kakao_b = options.get("kakao_b")

        # 추천인 생성
        if kakao_a:
            referrer, _ = User.objects.get_or_create(
                kakao_id=kakao_a, defaults={"type_code": None}
            )
        else:
            referrer = self._create_random_user(User)
            kakao_a = referrer.kakao_id

        # 피추천인 생성 (추천인과 다른 사용자)
        if kakao_b:
            referee, _ = User.objects.get_or_create(
                kakao_id=kakao_b, defaults={"type_code": None}
            )
        else:
            referee = self._create_random_user(User, exclude_kakao=kakao_a)
            kakao_b = referee.kakao_id

        if referrer.id == referee.id:
            raise CommandError("추천인과 피추천인이 동일합니다. 다른 kakao_id를 사용하세요.")

        # InviteCode 생성
        invite = ensure_invite_code(referrer)
        self.stdout.write(
            self.style.SUCCESS(
                f"[1] 추천인 생성: kakao_id={kakao_a}, 추천코드={invite.code}"
            )
        )

        # accept_referral
        try:
            referral, ref_issued = accept_referral(referee=referee, ref_code=invite.code)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[2] accept_referral 성공: referral_id={referral.id}, "
                    f"즉시 발급 쿠폰={len(ref_issued)}개"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[2] accept_referral 실패: {e}"))
            raise CommandError(str(e)) from e

        # qualify_referral_and_grant
        try:
            qual_ref, qual_issued = qualify_referral_and_grant(referee)
            total = len(ref_issued) + len(qual_issued)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[3] qualify_referral_and_grant 성공: "
                    f"추가 발급={len(qual_issued)}개, 총 발급={total}개"
                )
            )
            if qual_issued:
                for c in qual_issued[:5]:
                    self.stdout.write(f"    - 쿠폰: {c.code} (restaurant_id={c.restaurant_id})")
                if len(qual_issued) > 5:
                    self.stdout.write(f"    ... 외 {len(qual_issued) - 5}개")
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"[3] qualify_referral_and_grant: {e}")
            )

        self.stdout.write(self.style.SUCCESS("\n✓ 추천코드 발급 테스트 완료"))

    def _create_random_user(self, User, exclude_kakao=None):
        for _ in range(32):
            candidate = random.randint(910000000000, 999999999999)
            if exclude_kakao is not None and candidate == exclude_kakao:
                continue
            try:
                return User.objects.create(kakao_id=candidate, type_code=None)
            except IntegrityError:
                continue
        raise CommandError("사용 가능한 kakao_id를 찾지 못했습니다. --kakao-a, --kakao-b 를 지정하세요.")
