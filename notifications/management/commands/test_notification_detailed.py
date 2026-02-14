from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q

from guests.models import GuestUser
from notifications.utils import send_notification

User = get_user_model()


class Command(BaseCommand):
    help = "상세한 푸시 알림 테스트 - 업데이트한 사용자와 그렇지 않은 사용자 구분"

    def add_arguments(self, parser):
        parser.add_argument(
            '--send',
            action='store_true',
            help='실제로 알림을 전송합니다 (주의: 실제 알림이 전송됩니다!)',
        )
        parser.add_argument(
            '--sample-size',
            type=int,
            default=5,
            help='테스트할 샘플 토큰 수 (기본값: 5)',
        )

    def handle(self, *args, **options):
        send_actual = options.get('send', False)
        sample_size = options.get('sample_size', 5)

        if not send_actual:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  이 명령어는 실제 전송 테스트를 위한 것입니다.\n"
                    "   --send 옵션을 사용하면 실제 알림이 전송됩니다.\n"
                    "   먼저 샘플로 테스트하려면 --sample-size 옵션을 사용하세요."
                )
            )
            return

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("상세 푸시 알림 테스트 시작")
        self.stdout.write("=" * 80 + "\n")

        # 모든 토큰 수집
        guest_tokens = list(
            GuestUser.objects.exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .values_list("fcm_token", flat=True)
        )

        user_tokens = list(
            User.objects.exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .values_list("fcm_token", flat=True)
        )

        all_tokens = list(set(guest_tokens + user_tokens))
        
        self.stdout.write(f"📊 총 토큰 수: {len(all_tokens)}개")
        
        if len(all_tokens) == 0:
            self.stdout.write(
                self.style.ERROR("❌ 테스트할 토큰이 없습니다.")
            )
            return

        # 샘플링
        test_tokens = all_tokens[:sample_size] if len(all_tokens) > sample_size else all_tokens
        
        self.stdout.write(f"🧪 테스트할 토큰 수: {len(test_tokens)}개\n")
        
        # 실제 전송 테스트
        self.stdout.write("📤 실제 알림 전송 중...\n")
        result = send_notification(test_tokens, "상세 테스트 알림", dry_run=False)

        if not result:
            self.stdout.write(
                self.style.ERROR("❌ 알림 전송 실패: 결과를 가져올 수 없습니다.")
            )
            return

        success_count = result.get("success", 0)
        failure_count = result.get("failure", 0)
        failed_tokens = result.get("failed_tokens", [])

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("전송 결과")
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"✅ 성공: {success_count}개")
        self.stdout.write(f"❌ 실패: {failure_count}개\n")

        # 실패 분석
        sender_id_mismatch = []
        bad_environment = []
        other_errors = []

        for failed in failed_tokens:
            response = failed.get("response", {})
            if isinstance(response, dict):
                error = response.get("error", {})
                if isinstance(error, dict):
                    error_code = error.get("code")
                    message = error.get("message", "")
                    details = error.get("details", [])
                    
                    # SENDER_ID_MISMATCH 확인
                    fcm_error = None
                    for detail in details:
                        if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                            fcm_error = detail.get("errorCode")
                            break
                    
                    if fcm_error == "SENDER_ID_MISMATCH" or "SenderId mismatch" in message:
                        sender_id_mismatch.append(failed)
                    elif "BadEnvironmentKeyInToken" in str(details):
                        bad_environment.append(failed)
                    else:
                        other_errors.append(failed)

        if sender_id_mismatch:
            self.stdout.write(
                self.style.ERROR(f"\n❌ SENDER_ID_MISMATCH 오류: {len(sender_id_mismatch)}개")
            )
            self.stdout.write("   → iOS 앱의 GoogleService-Info.plist가 올바른 Firebase 프로젝트를 가리키지 않습니다.")
            self.stdout.write("   → 앱 업데이트가 필요한 사용자들입니다.\n")

        if bad_environment:
            self.stdout.write(
                self.style.ERROR(f"\n❌ BadEnvironmentKeyInToken 오류: {len(bad_environment)}개")
            )
            self.stdout.write("   → APNs 인증 키 환경 설정 문제입니다.\n")

        if other_errors:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️  기타 오류: {len(other_errors)}개")
            )

        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ {success_count}개의 토큰이 정상적으로 작동합니다!")
            )
            self.stdout.write("   → 이들은 올바른 Firebase 설정으로 앱을 업데이트한 사용자들일 가능성이 높습니다.\n")

        # 권장 사항
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("권장 사항")
        self.stdout.write("=" * 80 + "\n")
        
        if sender_id_mismatch:
            self.stdout.write("1. 앱 업데이트를 모든 사용자에게 권장하세요.")
            self.stdout.write("2. iOS 앱의 GoogleService-Info.plist가 올바른 Firebase 프로젝트를 가리키는지 확인하세요.")
            self.stdout.write("3. 업데이트 후 새 토큰이 생성되면 자동으로 문제가 해결됩니다.\n")

        if success_count > 0 and failure_count > 0:
            self.stdout.write(
                f"💡 현재 {success_count}명은 정상 작동하고, {failure_count}명은 앱 업데이트가 필요합니다."
            )

        self.stdout.write("=" * 80 + "\n")
















