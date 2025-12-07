from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from coupons.models import InviteCode
from coupons.service import ensure_invite_code

User = get_user_model()


class Command(BaseCommand):
    help = "운영진 계정에 이벤트 보상용 InviteCode 생성 (2개: SIGNUP, REFERRAL)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-id",
            type=int,
            required=True,
            help="운영진 계정의 카카오 ID",
        )
        parser.add_argument(
            "--code-signup",
            type=str,
            default=None,
            help="신규가입 타입 추천코드 (지정하지 않으면 자동 생성)",
        )
        parser.add_argument(
            "--code-referral",
            type=str,
            default=None,
            help="친구초대 타입 추천코드 (지정하지 않으면 자동 생성)",
        )

    def handle(self, *args, **options):
        kakao_id = options["kakao_id"]
        code_signup = options.get("code_signup")
        code_referral = options.get("code_referral")

        try:
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"카카오 ID {kakao_id}에 해당하는 사용자를 찾을 수 없습니다.")
            )
            return

        # 기존 InviteCode 확인 (일반 사용자용 기본 코드는 무시)
        existing_codes = InviteCode.objects.filter(user=user)
        if existing_codes.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"이미 {existing_codes.count()}개의 InviteCode가 존재합니다."
                )
            )

        # SIGNUP 타입 추천코드 생성
        if code_signup:
            # 지정된 코드로 생성
            invite_signup, created = InviteCode.objects.update_or_create(
                code=code_signup,
                defaults={
                    "user": user,
                    "campaign_code": "EVENT_REWARD_SIGNUP",
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"SIGNUP 타입 추천코드 생성: {invite_signup.code} (Campaign: EVENT_REWARD_SIGNUP)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"SIGNUP 타입 추천코드가 이미 존재합니다: {invite_signup.code}"
                    )
                )
        else:
            # 자동 생성 (기존 ensure_invite_code 로직 사용)
            # 하지만 campaign_code를 설정하기 위해 직접 생성
            from coupons.utils import make_coupon_code
            import uuid

            max_attempts = 32
            invite_signup = None
            for attempt in range(max_attempts):
                length = 12 if attempt >= 8 else 8
                code = make_coupon_code(length).upper()
                if InviteCode.objects.filter(code=code).exists():
                    continue
                try:
                    invite_signup = InviteCode.objects.create(
                        user=user, code=code, campaign_code="EVENT_REWARD_SIGNUP"
                    )
                    break
                except Exception:
                    continue

            if not invite_signup:
                # Fallback
                fallback_code = f"EVTS{user.id:06d}{uuid.uuid4().hex[:4].upper()}"
                invite_signup, _ = InviteCode.objects.update_or_create(
                    user=user,
                    defaults={"code": fallback_code[:16], "campaign_code": "EVENT_REWARD_SIGNUP"},
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"SIGNUP 타입 추천코드 생성: {invite_signup.code} (Campaign: EVENT_REWARD_SIGNUP)"
                )
            )

        # REFERRAL 타입 추천코드 생성
        if code_referral:
            invite_referral, created = InviteCode.objects.update_or_create(
                code=code_referral,
                defaults={
                    "user": user,
                    "campaign_code": "EVENT_REWARD_REFERRAL",
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"REFERRAL 타입 추천코드 생성: {invite_referral.code} (Campaign: EVENT_REWARD_REFERRAL)"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"REFERRAL 타입 추천코드가 이미 존재합니다: {invite_referral.code}"
                    )
                )
        else:
            # 자동 생성
            from coupons.utils import make_coupon_code
            import uuid

            max_attempts = 32
            invite_referral = None
            for attempt in range(max_attempts):
                length = 12 if attempt >= 8 else 8
                code = make_coupon_code(length).upper()
                if InviteCode.objects.filter(code=code).exists():
                    continue
                try:
                    invite_referral = InviteCode.objects.create(
                        user=user, code=code, campaign_code="EVENT_REWARD_REFERRAL"
                    )
                    break
                except Exception:
                    continue

            if not invite_referral:
                # Fallback
                fallback_code = f"EVTR{user.id:06d}{uuid.uuid4().hex[:4].upper()}"
                invite_referral, _ = InviteCode.objects.update_or_create(
                    user=user,
                    defaults={"code": fallback_code[:16], "campaign_code": "EVENT_REWARD_REFERRAL"},
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"REFERRAL 타입 추천코드 생성: {invite_referral.code} (Campaign: EVENT_REWARD_REFERRAL)"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n완료! 운영진 계정 (카카오 ID: {kakao_id})에 2개의 추천코드가 생성되었습니다."
            )
        )
        self.stdout.write(f"  - SIGNUP 타입: {invite_signup.code}")
        self.stdout.write(f"  - REFERRAL 타입: {invite_referral.code}")

