from django.core.management.base import BaseCommand

from coupons.pub_jujeom_event import ensure_pub_jujeom_event_data, resolve_cloudsql_alias


class Command(BaseCommand):
    help = "PUB_JUJEOM_EVENT CouponType·Campaign·benefit 을 CloudSQL(앱이 읽는 DB)에 반영"

    def handle(self, *args, **options):
        alias = ensure_pub_jujeom_event_data(db_alias=resolve_cloudsql_alias())
        self.stdout.write(self.style.SUCCESS(f"완료 (db={alias}). show_pub_jujeom_event_targets 로 확인하세요."))
