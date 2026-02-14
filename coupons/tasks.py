from celery import shared_task
from django.utils import timezone

from .models import Coupon


@shared_task
def expire_coupons():
    now = timezone.now()
    Coupon.objects.filter(
        status__in=["ISSUED", "EXPIRED"],
        expires_at__lt=now,
    ).delete()
