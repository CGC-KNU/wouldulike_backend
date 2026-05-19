from django.core.management.base import BaseCommand

from coupons.child_dept_event import ensure_child_dept_event_data
from coupons.festival_jungdunbam import resolve_cloudsql_alias


class Command(BaseCommand):
    help = "CHILD_DEPT_COUPON_PACK CouponType·Campaign·benefit 을 CloudSQL에 반영"

    def handle(self, *args, **options):
        alias = ensure_child_dept_event_data(db_alias=resolve_cloudsql_alias())
        self.stdout.write(self.style.SUCCESS(f"완료 (db={alias})"))
