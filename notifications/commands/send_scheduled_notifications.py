from django.core.management.base import BaseCommand
from django.utils import timezone

from guests.models import GuestUser
from notifications.models import Notification
from notifications.utils import send_notification


class Command(BaseCommand):
    help = 'Send scheduled push notifications to users.'

    def handle(self, *args, **options):
        now = timezone.now()
        notifications = Notification.objects.filter(scheduled_time__lte=now, sent=False)
        tokens = GuestUser.objects.exclude(fcm_token__isnull=True).exclude(fcm_token='').values_list('fcm_token', flat=True)
        for notification in notifications:
            send_notification(tokens, notification.content)
            notification.sent = True
            notification.save(update_fields=['sent'])
        self.stdout.write(self.style.SUCCESS(f'Sent {notifications.count()} notifications'))