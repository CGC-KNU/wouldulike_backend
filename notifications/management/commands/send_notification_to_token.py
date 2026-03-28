from django.core.management.base import BaseCommand

from notifications.utils import send_notification


class Command(BaseCommand):
    help = "특정 FCM 토큰에만 푸시 알림을 전송합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            required=True,
            help='알림을 보낼 FCM 토큰 (필수)',
        )
        parser.add_argument(
            '--message',
            type=str,
            required=True,
            help='알림 메시지 (필수)',
        )
        parser.add_argument(
            '--title',
            type=str,
            default=None,
            help='알림 제목 (미지정 시 본문 첫 줄을 제목으로 사용)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='드라이런 모드: 실제 전송 없이 검증만 수행',
        )

    def handle(self, *args, **options):
        token = options['token']
        message = options['message']
        title = options.get('title') or None
        dry_run = options.get('dry_run', False)
        title_preview = title if title else "(자동) 본문 첫 줄"

        if not token or not token.strip():
            self.stdout.write(
                self.style.ERROR("❌ 토큰이 제공되지 않았습니다.")
            )
            return

        if not message or not message.strip():
            self.stdout.write(
                self.style.ERROR("❌ 메시지가 제공되지 않았습니다.")
            )
            return

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("특정 토큰에 알림 전송")
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "🔍 드라이런 모드: 실제 FCM API를 호출하여 토큰 유효성을 검증합니다.\n"
                    "   ⚠️  주의: FCM API 호출 시 실제 알림이 전송될 수 있습니다."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  실제 알림 전송 모드입니다. 실제로 알림이 전송됩니다!"
                )
            )

        self.stdout.write(f"\n📱 대상 토큰: {token[:30]}...{token[-10:]}")
        self.stdout.write(f"📝 제목: {title_preview}")
        self.stdout.write(f"💬 메시지: {message}\n")

        # 알림 전송
        result = send_notification(
            tokens=[token],
            message=message,
            title=title,
            dry_run=dry_run
        )

        # 결과 출력
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("전송 결과")
        self.stdout.write("=" * 80 + "\n")

        if result is None:
            self.stdout.write(
                self.style.ERROR("❌ 전송 실패: 알림을 전송할 수 없습니다.")
            )
            return

        success_count = result.get("success", 0)
        failure_count = result.get("failure", 0)
        failed_tokens = result.get("failed_tokens", [])

        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ 알림 전송 성공!")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ 알림 전송 실패")
            )

        # 실패 상세 정보
        if failed_tokens:
            self.stdout.write("\n❌ 실패 상세:")
            for failed in failed_tokens:
                status_code = failed.get("status_code", "N/A")
                response = failed.get("response", {})
                error = response.get("error", {}) if isinstance(response, dict) else str(response)
                
                self.stdout.write(f"   상태 코드: {status_code}")
                if isinstance(error, dict):
                    error_message = error.get("message", "N/A")
                    self.stdout.write(f"   오류 메시지: {error_message}")
                    
                    # 오류 상세 분석
                    details = error.get("details", [])
                    for detail in details:
                        if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                            error_code = detail.get("errorCode")
                            self.stdout.write(f"   FCM 오류 코드: {error_code}")
                        elif detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.ApnsError":
                            apns_reason = detail.get("reason")
                            self.stdout.write(f"   APNs 오류: {apns_reason}")
                else:
                    self.stdout.write(f"   오류: {error}")

        self.stdout.write("\n" + "=" * 80 + "\n")

