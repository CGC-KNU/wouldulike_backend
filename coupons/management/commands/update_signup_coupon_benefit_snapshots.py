"""
신규가입 쿠폰(issue_key가 SIGNUP:으로 시작)의 benefit_snapshot에
issue_type_label="신규가입 쿠폰"을 추가합니다.

사용 예:
  python manage.py update_signup_coupon_benefit_snapshots --dry-run
  python manage.py update_signup_coupon_benefit_snapshots --no-input
"""
from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import Coupon

ISSUE_TYPE_LABEL = "신규가입 쿠폰"


class Command(BaseCommand):
    help = (
        "신규가입 쿠폰(issue_key가 SIGNUP:으로 시작)의 benefit_snapshot에 "
        "issue_type_label='신규가입 쿠폰'을 추가합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 수정하지 않고 수정 대상만 집계합니다.",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 없이 바로 수정합니다.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]

        alias = router.db_for_write(Coupon)

        qs = Coupon.objects.using(alias).filter(issue_key__startswith="SIGNUP:")
        total_count = qs.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS("신규가입 쿠폰(issue_key가 SIGNUP:으로 시작)이 없습니다.")
            )
            return

        # issue_type_label이 이미 있는 쿠폰 제외
        target_ids: list[int] = []
        for coupon in qs.iterator(chunk_size=1000):
            snap = coupon.benefit_snapshot or {}
            if snap.get("issue_type_label") == ISSUE_TYPE_LABEL:
                continue
            target_ids.append(coupon.id)

        if not target_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    f"모든 신규가입 쿠폰에 이미 issue_type_label='{ISSUE_TYPE_LABEL}'이 있습니다."
                )
            )
            return

        self.stdout.write("\n=== 신규가입 쿠폰 benefit_snapshot 업데이트 대상 ===")
        self.stdout.write(f"총 신규가입 쿠폰 수: {total_count}개")
        self.stdout.write(f"업데이트 대상 (issue_type_label 없음): {len(target_ids)}개\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 수정하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  위 {len(target_ids)}개의 쿠폰 benefit_snapshot에 "
                    f"issue_type_label='{ISSUE_TYPE_LABEL}'을 추가합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nbenefit_snapshot 업데이트 중...")

        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in Coupon.objects.using(alias).filter(id__in=target_ids).iterator(
                chunk_size=500
            ):
                snap = coupon.benefit_snapshot or {}
                if snap.get("issue_type_label") == ISSUE_TYPE_LABEL:
                    continue
                snap["issue_type_label"] = ISSUE_TYPE_LABEL
                coupon.benefit_snapshot = snap
                coupon.save(update_fields=["benefit_snapshot"], using=alias)
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n=== 업데이트 완료 ===\n"
                f"업데이트된 쿠폰 수: {updated_count}개\n"
                f"추가된 필드: issue_type_label='{ISSUE_TYPE_LABEL}'"
            )
        )
