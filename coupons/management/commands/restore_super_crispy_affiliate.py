"""슈퍼크리스피(298) 제휴 복구 및 축제 주막 이전 피해 감사."""
from django.core.management.base import BaseCommand

from coupons.super_crispy_restore import (
    PIN_ENV_KEYS,
    RESTAURANT_ID,
    audit_super_crispy,
    format_audit_report,
    resolve_super_crispy_pin_from_env,
    restore_super_crispy_affiliate,
)


class Command(BaseCommand):
    help = (
        f"restaurant_id={RESTAURANT_ID} 슈퍼크리스피 경북대점 제휴 복구. "
        "축제(298→299) 이전으로 덮인 필드·비활성 benefit 상태를 점검합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--audit-only",
            action="store_true",
            help="DB 상태만 출력하고 변경하지 않습니다.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="복구 예정 작업만 출력 (audit + dry-run restore).",
        )
        parser.add_argument(
            "--reset-pin",
            action="store_true",
            help="축제 PIN(0629)이면 pin/merchantpin 을 비운 뒤 --pin 으로 재설정.",
        )
        parser.add_argument(
            "--pin",
            type=str,
            default=None,
            help=(
                f"설정할 PIN. 생략 시 환경 변수 "
                f"{PIN_ENV_KEYS[0]} (또는 {PIN_ENV_KEYS[1]}) 사용."
            ),
        )

    def handle(self, *args, **options):
        audit_only = options["audit_only"]
        dry_run = options["dry_run"]
        reset_pin = options["reset_pin"]
        pin_arg = options.get("pin")
        if pin_arg is not None:
            pin = pin_arg.strip() or None
        else:
            pin = resolve_super_crispy_pin_from_env()

        self.stdout.write(self.style.MIGRATE_HEADING("=== 슈퍼크리스피(298) 감사 ==="))
        audit = audit_super_crispy()
        self.stdout.write(format_audit_report(audit))

        if audit_only:
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== 제휴 복구 ==="))
        if dry_run:
            restore_super_crispy_affiliate(dry_run=True, reset_pin=reset_pin, pin=pin)
            self.stdout.write(self.style.WARNING("[DRY-RUN] 변경 없음"))
            return

        restore_super_crispy_affiliate(dry_run=False, reset_pin=reset_pin, pin=pin)
        after = audit_super_crispy()
        self.stdout.write(self.style.SUCCESS("\n복구 후 상태:"))
        self.stdout.write(format_audit_report(after))
