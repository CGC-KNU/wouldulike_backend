from django.conf import settings
from pyfcm import FCMNotification


def send_notification(tokens, message):
    """Send push notification via FCM to the given tokens."""
    if not tokens:
        return
    api_key = getattr(settings, 'FCM_SERVER_KEY', None)
    if not api_key:
        return
    push_service = FCMNotification(api_key=api_key)
    push_service.notify_multiple_devices(registration_ids=list(tokens), message_body=message)