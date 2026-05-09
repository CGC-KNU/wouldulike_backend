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
        parser.add_argument(
            '--notification-id',
            type=int,
            help='전송할 특정 알림의 ID',
        )
        parser.add_argument(
            '--kakao-id',
            type=int,
            nargs='*',  # 0개 이상 허용
            help='알림을 보낼 사용자의 카카오 ID (여러 개 입력 가능, 위치 인자 kakao_ids와 동일한 기능)',
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        notification_id = options.get('notification_id')
        
        # 위치 인자 kakao_ids와 옵션 --kakao-id 모두 처리
        raw_kakao_ids = options.get("kakao_ids") or []
        kakao_id_option = options.get("kakao_id") or []
        
        # 두 소스를 합쳐서 filter_kakao_ids 생성
        all_raw_kakao_ids = list(raw_kakao_ids) + list(kakao_id_option)
        
        filter_kakao_ids = None
        if all_raw_kakao_ids:
            filter_kakao_ids = []
            for raw in all_raw_kakao_ids:
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
        
        # 특정 알림 ID로 필터링
        if notification_id:
            notifications = notifications.filter(id=notification_id)

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
            # 이 커맨드는 "예약 알림을 한 번 처리"하는 역할.
            # 토큰이 없거나 전송이 실패하더라도, 계속 sent=False로 남아 있으면
            # 다음 스케줄 실행에서 다른 알림과 함께 다시 시도되며 "의도치 않은 재발송"이 생길 수 있음.
            #
            # 따라서 (dry-run이 아닌 경우) 아래의 실패 경로에서도 sent=True로 마킹하여
            # 재처리 큐에서 빠지게 한다.
            # 대상 토큰 계산: target_kakao_ids 가 있으면 해당 사용자만, 없으면 전체
            if notification.target_kakao_ids:
                target_ids = notification.target_kakao_ids or []
                ids = target_ids
                if filter_kakao_ids is not None:
                    # 예약된 대상과, 커맨드로 지정된 대상의 교집합만 사용
                    ids = [kid for kid in target_ids if kid in filter_kakao_ids]

                users = User.objects.filter(kakao_id__in=ids)
                
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
                
                # 중복 제거
                tokens = list(set(user_tokens + guest_tokens))
                
                total_tokens = len(user_tokens) + len(guest_tokens)
                audience_label = (
                    f"specific kakao_ids ({len(ids)} ids, {len(tokens)} unique tokens, "
                    f"{len(user_tokens)} user + {len(guest_tokens)} guest)"
                )
            else:
                if filter_kakao_ids is not None:
                    # 전체 예약 알림이지만, 명시된 카카오 ID만 대상으로 전송
                    users = User.objects.filter(kakao_id__in=filter_kakao_ids)
                    
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
                    
                    # 중복 제거
                    tokens = list(set(user_tokens + guest_tokens))
                    
                    audience_label = (
                        f"filtered users by kakao_ids "
                        f"({len(filter_kakao_ids)} ids, {len(tokens)} unique tokens, "
                        f"{len(user_tokens)} user + {len(guest_tokens)} guest)"
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
                if not dry_run:
                    notification.sent = True
                    notification.save(update_fields=["sent"])
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
                if not dry_run:
                    notification.sent = True
                    notification.save(update_fields=["sent"])
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
                notification.sent = True
                notification.save(update_fields=["sent"])
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
            if not notification.sent_at:
                notification.sent_at = timezone.now()
                notification.save(update_fields=["sent", "sent_at"])
            else:
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
