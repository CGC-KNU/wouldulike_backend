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

            if response.get("failure"):
                failure_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Notification {notification.id} failed: {response}"
                    )
                )
                continue

            notification.sent = True
            notification.save(update_fields=["sent"])
            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} notifications (failed: {failure_count})"
            )
        )
