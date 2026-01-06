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
            "kakao_ids",
            nargs="*",
            help="특정 카카오 ID들만 대상으로 전송 (지정하지 않으면 전체 대상)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="드라이런 모드: 실제 전송 없이 검증만 수행",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        raw_kakao_ids = options.get("kakao_ids") or []

        filter_kakao_ids = None
        if raw_kakao_ids:
            filter_kakao_ids = []
            for raw in raw_kakao_ids:
                try:
                    filter_kakao_ids.append(int(raw))
                except ValueError:
                    self.stderr.write(
                        self.style.ERROR(f"유효하지 않은 카카오 ID 값입니다: {raw}")
                    )
                    return

        now = timezone.now()
        notifications = Notification.objects.filter(
            scheduled_time__lte=now,
            sent=False,
        )

        self.stdout.write(f"Found {notifications.count()} notification(s) to send")

        if not notifications.exists():
            self.stdout.write(self.style.WARNING("No notifications to send."))
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
            # 대상 토큰 계산: target_kakao_ids 가 있으면 해당 사용자만, 없으면 전체
            if notification.target_kakao_ids:
                target_ids = notification.target_kakao_ids or []
                ids = target_ids
                if filter_kakao_ids is not None:
                    # 예약된 대상과, 커맨드로 지정된 대상의 교집합만 사용
                    ids = [kid for kid in target_ids if kid in filter_kakao_ids]

                users_qs = User.objects.filter(kakao_id__in=ids).exclude(
                    fcm_token__isnull=True
                ).exclude(fcm_token="")

                tokens = list(
                    users_qs.values_list("fcm_token", flat=True).distinct()
                )

                audience_label = (
                    f"specific kakao_ids ({len(ids)} ids, {len(tokens)} tokens)"
                )
            else:
                if filter_kakao_ids is not None:
                    # 전체 예약 알림이지만, 명시된 카카오 ID만 대상으로 전송
                    users_qs = User.objects.filter(
                        kakao_id__in=filter_kakao_ids
                    ).exclude(fcm_token__isnull=True).exclude(fcm_token="")

                    tokens = list(
                        users_qs.values_list("fcm_token", flat=True).distinct()
                    )
                    audience_label = (
                        f"filtered users by kakao_ids "
                        f"({len(filter_kakao_ids)} ids, {len(tokens)} tokens)"
                    )
                else:
                    # GuestUser와 User 모두에서 FCM 토큰 수집 (전체 발송)
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

                    # 중복 제거 (같은 토큰이 여러 사용자에게 있을 수 있음)
                    tokens = list(set(guest_tokens + user_tokens))
                    audience_label = (
                        f"all users ({len(guest_tokens)} guest, "
                        f"{len(user_tokens)} user tokens)"
                    )

            self.stdout.write(
                f"\nProcessing notification {notification.id} "
                f"[audience: {audience_label}, unique tokens: {len(tokens)}]"
            )

            if not tokens:
                self.stdout.write(
                    self.style.WARNING(
                        f"Notification {notification.id} has no valid tokens; skipping."
                    )
                )
                failure_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Validating notification {notification.id}: "
                    f"{notification.content[:50]}..."
                )
            else:
                self.stdout.write(
                    f"Sending notification {notification.id}: "
                    f"{notification.content[:50]}..."
                )

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
                            f"Notification {notification.id} validation failed: "
                            f"{response.get('issues', [])}"
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
                        if (
                            detail.get("@type")
                            == "type.googleapis.com/google.firebase.fcm.v1.FcmError"
                        ):
                            error_code = detail.get("errorCode")
                            break
                    status = error.get("status")
                    if error_code == "UNREGISTERED" or status == "NOT_FOUND":
                        invalid_tokens.append(token)

                if invalid_tokens:
                    # GuestUser와 User 모두에서 무효한 토큰 제거
                    guest_removed = GuestUser.objects.filter(
                        fcm_token__in=invalid_tokens
                    ).update(fcm_token="")
                    user_removed = User.objects.filter(
                        fcm_token__in=invalid_tokens
                    ).update(fcm_token="")
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
