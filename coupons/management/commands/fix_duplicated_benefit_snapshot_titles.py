from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import Coupon


DUP_TITLE = "커피명가 커피명가 커피 전메뉴 1+1"
NORMAL_TITLE = "커피명가 커피 전메뉴 1+1"


class Command(BaseCommand):
    help = (
        "benefit_snapshot.title 이 중복된 '커피명가 커피명가 커피 전메뉴 1+1' 인 쿠폰을 "
        "정상 값 '커피명가 커피 전메뉴 1+1' 로 정리합니다."
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

        qs = Coupon.objects.using(alias).filter(
            benefit_snapshot__title=DUP_TITLE,
        )

        total_count = qs.count()
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"benefit_snapshot.title 이 '{DUP_TITLE}' 인 쿠폰이 없습니다."
                )
            )
            return

        self.stdout.write("\n=== 중복 benefit_snapshot.title 정리 대상 ===")
        self.stdout.write(f"대상 쿠폰 수: {total_count}개\n")

        # 샘플 출력
        self.stdout.write("샘플 10개 (code, coupon_type, campaign, restaurant_id, title):")
        sample = list(
            qs.select_related("coupon_type", "campaign")[:10].values(
                "code",
                "coupon_type__code",
                "campaign__code",
                "restaurant_id",
                "benefit_snapshot",
            )
        )
        for row in sample:
            snap = row["benefit_snapshot"] or {}
            title = snap.get("title")
            self.stdout.write(
                f"  - code={row['code']}, "
                f"type={row['coupon_type__code']}, "
                f"camp={row['campaign__code']}, "
                f"restaurant_id={row['restaurant_id']}, "
                f"title={title!r}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 수정하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  위 {total_count}개의 쿠폰 benefit_snapshot.title 을 "
                    f"'{DUP_TITLE}' → '{NORMAL_TITLE}' 로 수정합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nbenefit_snapshot.title 정리 중...")

        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in qs.iterator(chunk_size=500):
                snap = coupon.benefit_snapshot or {}
                if snap.get("title") != DUP_TITLE:
                    continue
                snap["title"] = NORMAL_TITLE
                coupon.benefit_snapshot = snap
                coupon.save(update_fields=["benefit_snapshot"], using=alias)
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\n=== 업데이트 완료 ===\n"
                f"업데이트된 쿠폰 수: {updated_count}개\n"
                f"치환: '{DUP_TITLE}' → '{NORMAL_TITLE}'"
            )
        )






