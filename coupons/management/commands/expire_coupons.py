from django.core.management.base import BaseCommand
from django.utils import timezone

from coupons.models import Coupon


class Command(BaseCommand):
    help = "Mark expired coupons as EXPIRED"

    def handle(self, *args, **kwargs):
        now = timezone.now()
        n = Coupon.objects.filter(status="ISSUED", expires_at__lt=now).update(status="EXPIRED")
        self.stdout.write(self.style.SUCCESS(f"Expired {n} coupons"))
