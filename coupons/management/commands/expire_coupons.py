from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count

from coupons.models import Coupon


class Command(BaseCommand):
    help = "Delete expired coupons"

    def handle(self, *args, **kwargs):
        now = timezone.now()
        expired_qs = Coupon.objects.filter(
            status__in=["ISSUED", "EXPIRED"],
            expires_at__lt=now,
        )

        total_all = Coupon.objects.count()
        total_expired = expired_qs.count()
        by_status = (
            Coupon.objects.values("status")
            .annotate(cnt=Count("id"))
            .order_by("status")
        )
        by_type = (
            expired_qs.values("coupon_type__code")
            .annotate(cnt=Count("id"))
            .order_by("coupon_type__code")
        )

        self.stdout.write(f"총 쿠폰 수: {total_all}")
        self.stdout.write(f"삭제 대상 만료 쿠폰 수: {total_expired}")
        self.stdout.write("상태별 쿠폰 수:")
        for row in by_status:
            self.stdout.write(f"- {row['status']}: {row['cnt']}")
        self.stdout.write("삭제 대상 쿠폰 종류별 수:")
        for row in by_type:
            code = row["coupon_type__code"] or "UNKNOWN"
            self.stdout.write(f"- {code}: {row['cnt']}")

        if total_expired == 0:
            self.stdout.write(self.style.WARNING("삭제할 만료 쿠폰이 없습니다."))
            return

        confirm = input("만료 쿠폰을 삭제하려면 'yes'를 입력하세요: ")
        if confirm.strip().lower() != "yes":
            self.stdout.write(self.style.WARNING("삭제를 취소했습니다."))
            return

        deleted, _ = expired_qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired coupons"))
