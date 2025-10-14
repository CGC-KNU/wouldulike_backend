from django.core.management.base import BaseCommand
from django.utils import timezone

from guests.models import GuestUser
from notifications.models import Notification
from notifications.utils import send_notification


class Command(BaseCommand):
    help = "Send scheduled push notifications to users."

    def handle(self, *args, **options):
        now = timezone.now()
        notifications = Notification.objects.filter(
            scheduled_time__lte=now,
            sent=False,
        )
        tokens = list(
            GuestUser.objects.exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .values_list("fcm_token", flat=True)
        )

        if not tokens:
            self.stdout.write(
                self.style.WARNING("No valid FCM tokens found; skipping send.")
            )
            return

        sent_count = 0
        failure_count = 0
        partial_count = 0
        for notification in notifications:
            response = send_notification(tokens, notification.content)

            if not response:
                failure_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Notification {notification.id} failed to send (no response)"
                    )
                )
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
                    GuestUser.objects.filter(fcm_token__in=invalid_tokens).update(
                        fcm_token=""
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"Removed {len(invalid_tokens)} invalid FCM tokens"
                        )
                    )

            notification.sent = True
            notification.save(update_fields=["sent"])
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} notifications "
                f"(failed: {failure_count}, partial: {partial_count})"
            )
        )
