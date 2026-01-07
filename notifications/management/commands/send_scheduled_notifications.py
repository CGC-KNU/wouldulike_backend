from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from guests.models import GuestUser
from notifications.models import Notification
from notifications.utils import send_notification

User = get_user_model()


class Command(BaseCommand):
    help = "Send scheduled push notifications to users."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='드라이런 모드: 실제 전송 없이 검증만 수행',
        )
        parser.add_argument(
            '--notification-id',
            type=int,
            help='전송할 특정 알림의 ID',
        )
        parser.add_argument(
            '--kakao-id',
            type=int,
            nargs='*',  # 0개 이상 허용
            help='알림을 보낼 사용자의 카카오 ID (여러 개 입력 가능)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        notification_id = options.get('notification_id')
        kakao_ids = options.get('kakao_id')
        
        now = timezone.now()
        notifications = Notification.objects.filter(
            scheduled_time__lte=now,
            sent=False,
        )
        
        # 특정 알림 ID로 필터링
        if notification_id:
            notifications = notifications.filter(id=notification_id)
        
        self.stdout.write(f"Found {notifications.count()} notification(s) to send")
        
        # 특정 카카오 ID로 필터링된 토큰 수집
        if kakao_ids:
            self.stdout.write(f"\n특정 카카오 ID 사용자 {len(kakao_ids)}명에게만 전송합니다.")
            
            users = User.objects.filter(kakao_id__in=kakao_ids)
            found_users = users.count()
            
            if found_users == 0:
                self.stdout.write(
                    self.style.ERROR("❌ 지정된 카카오 ID에 해당하는 사용자를 찾을 수 없습니다.")
                )
                return
            
            self.stdout.write(f"\n✅ 사용자 조회 성공: {found_users}명")
            
            # User의 FCM 토큰 수집
            user_tokens = list(
                users.exclude(fcm_token__isnull=True)
                .exclude(fcm_token="")
                .values_list("fcm_token", flat=True)
            )
            
            # 연결된 GuestUser의 FCM 토큰 수집
            guest_tokens = list(
                GuestUser.objects.filter(linked_user__in=users)
                .exclude(fcm_token__isnull=True)
                .exclude(fcm_token="")
                .values_list("fcm_token", flat=True)
            )
            
            total_tokens = len(user_tokens) + len(guest_tokens)
            self.stdout.write(f"📱 FCM 토큰 보유: {total_tokens}개 (User + 연결된 GuestUser)")
            
            # 토큰이 없는 사용자 확인
            users_without_tokens = []
            for user in users:
                user_token = user.fcm_token if user.fcm_token else None
                guest_tokens_for_user = list(
                    GuestUser.objects.filter(linked_user=user)
                    .exclude(fcm_token__isnull=True)
                    .exclude(fcm_token="")
                    .values_list("fcm_token", flat=True)
                )
                if not user_token and not guest_tokens_for_user:
                    users_without_tokens.append(user.kakao_id)
            
            if users_without_tokens:
                self.stdout.write(f"\n⚠️  조회 실패 또는 토큰 없음: {len(users_without_tokens)}명")
                for kakao_id in users_without_tokens:
                    self.stdout.write(f"   - 카카오 ID {kakao_id}: User와 연결된 GuestUser 모두 FCM 토큰이 없습니다.")
            
            # 중복 제거
            tokens = list(set(user_tokens + guest_tokens))
        else:
            # 모든 사용자에게 전송 (기존 로직)
            # GuestUser와 User 모두에서 FCM 토큰 수집
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
            
            self.stdout.write(f"Found {len(guest_tokens)} guest tokens and {len(user_tokens)} user tokens")
            
            # 중복 제거 (같은 토큰이 여러 사용자에게 있을 수 있음)
            tokens = list(set(guest_tokens + user_tokens))
        
        self.stdout.write(f"Total unique tokens: {len(tokens)}")

        if not tokens:
            self.stdout.write(
                self.style.WARNING("No valid FCM tokens found; skipping send.")
            )
            return
        
        if not notifications.exists():
            self.stdout.write(
                self.style.WARNING("No notifications to send.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  드라이런 모드: 실제 알림은 전송되지 않습니다.\n"
                )
            )

        sent_count = 0
        failure_count = 0
        partial_count = 0
        for notification in notifications:
            if dry_run:
                self.stdout.write(f"\n[DRY-RUN] Validating notification {notification.id}: {notification.content[:50]}...")
            else:
                self.stdout.write(f"\nSending notification {notification.id}: {notification.content[:50]}...")
            response = send_notification(tokens, notification.content, dry_run=dry_run)

            if not response:
                failure_count += 1
                if dry_run:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Notification {notification.id} validation failed (no response). "
                            "Check FCM configuration (FCM_PROJECT_ID, FCM_SERVICE_ACCOUNT_FILE/JSON)."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Notification {notification.id} failed to send (no response). "
                            "Check FCM configuration (FCM_PROJECT_ID, FCM_SERVICE_ACCOUNT_FILE/JSON)."
                        )
                    )
                continue

            if dry_run:
                # 드라이런 모드 결과 처리
                is_valid = response.get("valid", False)
                if not is_valid:
                    failure_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Notification {notification.id} validation failed: {response.get('issues', [])}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Notification {notification.id} validation passed: "
                            f"{response.get('valid_tokens_count', 0)} valid tokens"
                        )
                    )
                # 드라이런 모드에서는 sent 플래그를 업데이트하지 않음
                continue

            failures = response.get("failure", 0) or 0
            successes = response.get("success", 0) or 0
            failed_tokens = response.get("failed_tokens", [])

            if successes == 0:
                failure_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Notification {notification.id} failed: {response}"
                    )
                )
                continue

            if failures:
                partial_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Notification {notification.id} partially failed: {response}"
                    )
                )

                # Clean up invalid tokens such as UNREGISTERED responses.
                invalid_tokens = []
                for failed in failed_tokens:
                    token = failed.get("token")
                    error = failed.get("response", {}).get("error", {}) if failed.get(
                        "response"
                    ) else {}
                    error_code = ""
                    for detail in error.get("details", []):
                        if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                            error_code = detail.get("errorCode")
                            break
                    status = error.get("status")
                    if error_code == "UNREGISTERED" or status == "NOT_FOUND":
                        invalid_tokens.append(token)

                if invalid_tokens:
                    # GuestUser와 User 모두에서 무효한 토큰 제거
                    guest_removed = GuestUser.objects.filter(fcm_token__in=invalid_tokens).update(
                        fcm_token=""
                    )
                    user_removed = User.objects.filter(fcm_token__in=invalid_tokens).update(
                        fcm_token=""
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"Removed {len(invalid_tokens)} invalid FCM tokens "
                            f"(GuestUser: {guest_removed}, User: {user_removed})"
                        )
                    )

            notification.sent = True
            notification.save(update_fields=["sent"])
            sent_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ 검증 완료: {sent_count}개 알림 검증됨 "
                    f"(실패: {failure_count}, 부분 실패: {partial_count})"
                )
            )
            self.stdout.write(
                "\n💡 실제 알림을 전송하려면 --dry-run 옵션 없이 실행하세요."
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sent {sent_count} notifications "
                    f"(failed: {failure_count}, partial: {partial_count})"
                )
            )
