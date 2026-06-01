"""슈퍼크리스피(298) 제휴 복구 및 축제 주막 이전 피해 감사."""
from django.core.management.base import BaseCommand

from coupons.super_crispy_restore import (
    PIN_ENV_KEYS,
    RESTAURANT_ID,
    audit_super_crispy,
    complete_super_crispy_recovery,
    format_audit_report,
    recover_super_crispy_merchant_data,
    resolve_super_crispy_pin_from_env,
    restore_super_crispy_affiliate,
    verify_super_crispy_against_contract,
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
        parser.add_argument(
            "--merchant-only",
            action="store_true",
            help="제휴 행·PIN 없이 쿠폰·스탬프·summary 만 복구합니다.",
        )
        parser.add_argument(
            "--skip-merchant",
            action="store_true",
            help="제휴 행만 복구하고 쿠폰·스탬프 복구는 건너뜁니다.",
        )
        parser.add_argument(
            "--verify-contract",
            action="store_true",
            help="CSV 계약 대비 DB 상태만 검증합니다.",
        )

    def handle(self, *args, **options):
        audit_only = options["audit_only"]
        dry_run = options["dry_run"]
        reset_pin = options["reset_pin"]
        merchant_only = options["merchant_only"]
        skip_merchant = options["skip_merchant"]
        pin_arg = options.get("pin")
        if pin_arg is not None:
            pin = pin_arg.strip() or None
        else:
            pin = resolve_super_crispy_pin_from_env()

        self.stdout.write(self.style.MIGRATE_HEADING("=== 슈퍼크리스피(298) 감사 ==="))
        audit = audit_super_crispy()
        self.stdout.write(format_audit_report(audit))

        if options["verify_contract"]:
            issues = verify_super_crispy_against_contract()
            if issues:
                self.stdout.write(self.style.ERROR("\n계약 불일치:"))
                for line in issues:
                    self.stdout.write(f"  - {line}")
            else:
                self.stdout.write(self.style.SUCCESS("\nCSV 계약과 일치합니다."))
            return

        if audit_only:
            return

        if merchant_only:
            self.stdout.write(self.style.MIGRATE_HEADING("=== 쿠폰·스탬프·적립 복구 ==="))
            if dry_run:
                recover_super_crispy_merchant_data(dry_run=True)
                self.stdout.write(self.style.WARNING("[DRY-RUN] 변경 없음"))
                return
            recover_super_crispy_merchant_data(dry_run=False)
        elif not skip_merchant and not dry_run:
            self.stdout.write(self.style.MIGRATE_HEADING("=== 전체 복구 (제휴+CSV+적립) ==="))
            complete_super_crispy_recovery(dry_run=False, pin=pin)
            issues = verify_super_crispy_against_contract()
            if issues:
                self.stdout.write(self.style.WARNING("\n계약 검증 (남은 항목):"))
                for line in issues:
                    self.stdout.write(f"  - {line}")
        else:
            self.stdout.write(self.style.MIGRATE_HEADING("=== 제휴 복구 ==="))
            if dry_run:
                restore_super_crispy_affiliate(
                    dry_run=True,
                    reset_pin=reset_pin,
                    pin=pin,
                    recover_merchant_data=not skip_merchant,
                )
                self.stdout.write(self.style.WARNING("[DRY-RUN] 변경 없음"))
                return

            restore_super_crispy_affiliate(
                dry_run=False,
                reset_pin=reset_pin,
                pin=pin,
                recover_merchant_data=not skip_merchant,
            )

        after = audit_super_crispy()
        self.stdout.write(self.style.SUCCESS("\n복구 후 상태:"))
        self.stdout.write(format_audit_report(after))
