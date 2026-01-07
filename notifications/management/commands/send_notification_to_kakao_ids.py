from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from notifications.utils import send_notification


User = get_user_model()


class Command(BaseCommand):
    help = "특정 카카오 ID(들)에 연결된 FCM 토큰으로 알림을 전송합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "kakao_ids",
            nargs="+",
            help="알림을 보낼 대상 카카오 ID 목록 (공백으로 구분)",
        )
        parser.add_argument(
            "--message",
            type=str,
            required=True,
            help="전송할 알림 메시지 내용",
        )
        parser.add_argument(
            "--title",
            type=str,
            default="우주라이크",
            help='알림 제목 (기본값: "우주라이크")',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="드라이런 모드: 실제 전송 대신 FCM 요청만 시도하고 결과만 확인",
        )

    def handle(self, *args, **options):
        raw_kakao_ids = options["kakao_ids"]
        message = options["message"]
        title = options.get("title") or "우주라이크"
        dry_run = options.get("dry_run", False)

        # 숫자 형식으로 변환
        kakao_ids = []
        for raw in raw_kakao_ids:
            try:
                kakao_ids.append(int(raw))
            except ValueError:
                raise CommandError(f"유효하지 않은 카카오 ID 값입니다: {raw}")

        users = (
            User.objects.filter(kakao_id__in=kakao_ids)
            .exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .only("id", "kakao_id", "fcm_token")
        )

        found_ids = {u.kakao_id for u in users}
        missing_ids = [kid for kid in kakao_ids if kid not in found_ids]

        if missing_ids:
            self.stdout.write(
                self.style.WARNING(
                    f"다음 카카오 ID는 존재하지 않거나 FCM 토큰이 없습니다: {missing_ids}"
                )
            )

        tokens = list({u.fcm_token for u in users if u.fcm_token})

        self.stdout.write(
            self.style.SUCCESS(
                f"대상 카카오 ID 수: {len(kakao_ids)}개, "
                f"실제 전송 대상 사용자 수: {users.count()}명, "
                f"고유 FCM 토큰 수: {len(tokens)}개"
            )
        )

        if not tokens:
            self.stdout.write(
                self.style.ERROR(
                    "전송할 수 있는 FCM 토큰이 없습니다. 대상 사용자의 fcm_token 값을 확인하세요."
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️ 드라이런 모드로 실행됩니다. 실제 운영 메시지 대신 테스트 메시지가 전송될 수 있습니다."
                )
            )

        self.stdout.write(
            f"알림 제목: {title}\n"
            f"알림 메시지(앞 80자): {message[:80]}{'...' if len(message) > 80 else ''}\n"
        )

        result = send_notification(tokens, message, dry_run=dry_run, title=title)

        if not result:
            self.stdout.write(
                self.style.ERROR(
                    "❌ FCM 요청에 실패했습니다. FCM 설정(프로젝트 ID, 서비스 계정 등)을 확인하세요."
                )
            )
            return

        success = result.get("success", 0)
        failure = result.get("failure", 0)

        self.stdout.write(
            self.style.SUCCESS(f"✅ 전송 완료 - 성공: {success}개, 실패: {failure}개")
        )

        if failure:
            self.stdout.write(
                self.style.WARNING(
                    "일부 토큰 전송에 실패했습니다. 자세한 내용은 로그 또는 result['failed_tokens']를 확인하세요."
                )
            )


