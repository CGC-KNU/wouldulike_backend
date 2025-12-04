from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from guests.models import GuestUser
from notifications.utils import validate_notification, send_notification

User = get_user_model()


class Command(BaseCommand):
    help = "테스트 모드로 푸시 알림 설정을 검증합니다. 실제 알림은 전송되지 않습니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--message',
            type=str,
            default='테스트 알림 메시지입니다.',
            help='테스트할 알림 메시지 (기본값: "테스트 알림 메시지입니다.")',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='특정 FCM 토큰으로 테스트 (지정하지 않으면 DB의 모든 토큰 사용)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=True,
            help='드라이런 모드: 실제 전송 없이 검증만 수행 (기본값)',
        )
        parser.add_argument(
            '--send',
            action='store_true',
            help='실제로 알림을 전송합니다 (주의: --dry-run과 함께 사용 불가)',
        )

    def handle(self, *args, **options):
        message = options['message']
        test_token = options.get('token')
        send_actual = options.get('send', False)
        # --send가 명시되지 않으면 항상 드라이런 모드
        dry_run = not send_actual

        # --send 옵션이 있으면 실제 전송 모드
        if send_actual:
            dry_run = False
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  실제 알림 전송 모드입니다. 실제로 알림이 전송됩니다!"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "🔍 테스트 모드 (드라이런): 실제 FCM API를 호출하여 토큰 유효성을 검증합니다.\n"
                    "   ⚠️  주의: FCM API 호출 시 실제 알림이 전송될 수 있습니다.\n"
                    "   하지만 테스트 목적으로 실제 API 응답을 통해 토큰 유효성을 검증합니다."
                )
            )

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("푸시 알림 설정 검증 시작")
        self.stdout.write("=" * 80 + "\n")

        # 토큰 수집
        if test_token:
            tokens = [test_token]
            self.stdout.write(f"📱 지정된 토큰 사용: {test_token[:30]}...")
        else:
            # DB에서 모든 토큰 수집
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

            tokens = list(set(guest_tokens + user_tokens))
            self.stdout.write(f"📊 GuestUser 토큰: {len(guest_tokens)}개")
            self.stdout.write(f"📊 User 토큰: {len(user_tokens)}개")
            self.stdout.write(f"📊 총 고유 토큰: {len(tokens)}개\n")

        if not tokens:
            self.stdout.write(
                self.style.ERROR(
                    "❌ FCM 토큰을 찾을 수 없습니다.\n"
                    "   - DB에 FCM 토큰이 저장되어 있는지 확인하세요.\n"
                    "   - 또는 --token 옵션으로 특정 토큰을 지정하세요."
                )
            )
            return

        # 검증 수행
        if dry_run:
            self.stdout.write("🔍 실제 FCM API 호출하여 토큰 유효성 검증 중...\n")
            self.stdout.write("   (실제 API 호출이므로 알림이 전송될 수 있습니다)\n\n")
            result = send_notification(tokens, message, dry_run=True)
        else:
            self.stdout.write("⚠️  실제 알림 전송을 시작합니다...\n\n")
            result = send_notification(tokens, message, dry_run=False)

        # 결과 출력
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("검증 결과")
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            # 드라이런 모드 결과 출력
            self._print_dry_run_results(result)
        else:
            # 실제 전송 결과 출력
            self._print_send_results(result)

    def _print_dry_run_results(self, result):
        """드라이런 모드 결과 출력"""
        if result is None:
            self.stdout.write(
                self.style.ERROR("❌ 검증 실패: 결과를 가져올 수 없습니다.")
            )
            return

        # 드라이런 모드에서는 실제 API 호출 결과를 표시
        if result.get("dry_run"):
            note = result.get("note", "")
            if note:
                self.stdout.write(f"\n📝 {note}\n")

        success_count = result.get("success", 0)
        failure_count = result.get("failure", 0)
        failed_tokens = result.get("failed_tokens", [])

        self.stdout.write("\n📊 실제 FCM API 호출 결과:")
        self.stdout.write(
            self.style.SUCCESS(f"   ✅ 성공: {success_count}개")
        )
        if failure_count > 0:
            self.stdout.write(
                self.style.ERROR(f"   ❌ 실패: {failure_count}개")
            )

        # 실패 분석
        sender_id_mismatch = []
        bad_environment = []
        unregistered = []
        other_errors = []

        for failed in failed_tokens:
            response = failed.get("response", {})
            if isinstance(response, dict):
                error = response.get("error", {})
                if isinstance(error, dict):
                    message = error.get("message", "")
                    details = error.get("details", [])
                    
                    # 오류 유형 확인
                    fcm_error = None
                    apns_error = None
                    for detail in details:
                        if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                            fcm_error = detail.get("errorCode")
                        elif detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.ApnsError":
                            apns_error = detail.get("reason")
                    
                    if fcm_error == "SENDER_ID_MISMATCH" or "SenderId mismatch" in message:
                        sender_id_mismatch.append(failed)
                    elif fcm_error == "UNREGISTERED":
                        unregistered.append(failed)
                    elif apns_error == "BadEnvironmentKeyInToken" or "BadEnvironmentKeyInToken" in str(details):
                        bad_environment.append(failed)
                    else:
                        other_errors.append(failed)

        # 오류 상세 분석
        if sender_id_mismatch:
            self.stdout.write(
                self.style.ERROR(f"\n❌ SENDER_ID_MISMATCH 오류: {len(sender_id_mismatch)}개")
            )
            self.stdout.write("   → iOS 앱의 GoogleService-Info.plist가 올바른 Firebase 프로젝트를 가리키지 않습니다.")
            self.stdout.write("   → 앱 업데이트가 필요한 사용자들입니다.")

        if bad_environment:
            self.stdout.write(
                self.style.ERROR(f"\n❌ BadEnvironmentKeyInToken 오류: {len(bad_environment)}개")
            )
            self.stdout.write("   → APNs 인증 키 환경 설정 문제입니다.")

        if unregistered:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️  UNREGISTERED 토큰: {len(unregistered)}개")
            )
            self.stdout.write("   → 등록되지 않은 토큰입니다. DB에서 제거하는 것을 권장합니다.")

        if other_errors:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️  기타 오류: {len(other_errors)}개")
            )

        # 실패한 토큰 상세 (최대 10개)
        if failed_tokens:
            self.stdout.write("\n❌ 실패한 토큰 상세 (최대 10개):")
            for failed in failed_tokens[:10]:
                token = failed.get("token", "N/A")
                status_code = failed.get("status_code", "N/A")
                response = failed.get("response", {})
                error = response.get("error", {}) if isinstance(response, dict) else str(response)
                
                self.stdout.write(
                    self.style.ERROR(f"   • {token[:30]}...")
                )
                self.stdout.write(f"     상태 코드: {status_code}")
                if isinstance(error, dict):
                    self.stdout.write(f"     오류 메시지: {error.get('message', 'N/A')}")
                else:
                    self.stdout.write(f"     오류: {error}")
            
            if len(failed_tokens) > 10:
                self.stdout.write(f"   ... 외 {len(failed_tokens) - 10}개")

        # 최종 상태
        self.stdout.write("\n" + "=" * 80)
        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ {success_count}개의 토큰이 정상적으로 작동합니다!")
            )
            if failure_count > 0:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {failure_count}개의 토큰에서 문제가 발견되었습니다.")
                )
        else:
            self.stdout.write(
                self.style.ERROR("❌ 모든 토큰에서 문제가 발견되었습니다.")
            )
        
        if result.get("dry_run"):
            self.stdout.write(
                "\n💡 이 테스트는 실제 FCM API를 호출하여 토큰 유효성을 검증했습니다."
            )
            self.stdout.write("   실제 알림을 전송하려면 --send 옵션을 사용하세요:")
            self.stdout.write("   python manage.py test_notification --send")
        
        self.stdout.write("=" * 80 + "\n")

    def _print_send_results(self, result):
        """실제 전송 결과 출력"""
        if result is None:
            self.stdout.write(
                self.style.ERROR("❌ 전송 실패: 알림을 전송할 수 없습니다.")
            )
            return

        success_count = result.get("success", 0)
        failure_count = result.get("failure", 0)
        failed_tokens = result.get("failed_tokens", [])

        self.stdout.write("\n📊 전송 결과:")
        self.stdout.write(
            self.style.SUCCESS(f"   ✅ 성공: {success_count}개")
        )
        if failure_count > 0:
            self.stdout.write(
                self.style.ERROR(f"   ❌ 실패: {failure_count}개")
            )

        # 실패한 토큰 상세 (최대 10개)
        if failed_tokens:
            self.stdout.write("\n❌ 실패한 토큰 상세:")
            for failed in failed_tokens[:10]:
                token = failed.get("token", "N/A")
                status_code = failed.get("status_code", "N/A")
                response = failed.get("response", {})
                error = response.get("error", {}) if isinstance(response, dict) else str(response)
                
                self.stdout.write(
                    self.style.ERROR(f"   • {token[:30]}...")
                )
                self.stdout.write(f"     상태 코드: {status_code}")
                self.stdout.write(f"     오류: {error}")
            
            if len(failed_tokens) > 10:
                self.stdout.write(f"   ... 외 {len(failed_tokens) - 10}개")

        # 무효한 토큰 정리 안내
        unregistered_tokens = []
        for failed in failed_tokens:
            response = failed.get("response", {})
            if isinstance(response, dict):
                error = response.get("error", {})
                if isinstance(error, dict):
                    for detail in error.get("details", []):
                        if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                            if detail.get("errorCode") == "UNREGISTERED":
                                unregistered_tokens.append(failed.get("token"))
                                break

        if unregistered_tokens:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  {len(unregistered_tokens)}개의 등록되지 않은 토큰이 발견되었습니다. "
                    "이 토큰들은 DB에서 제거하는 것을 권장합니다."
                )
            )

        self.stdout.write("\n" + "=" * 80)
        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ 알림 전송 완료: {success_count}개 성공")
            )
        else:
            self.stdout.write(
                self.style.ERROR("❌ 알림 전송 실패: 모든 토큰에서 실패했습니다.")
            )
        self.stdout.write("=" * 80 + "\n")

