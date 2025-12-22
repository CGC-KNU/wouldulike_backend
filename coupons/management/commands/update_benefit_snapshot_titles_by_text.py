from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import Coupon


DEFAULT_OLD_TEXT = "커피 전메뉴 1+1"
DEFAULT_NEW_TEXT = "커피명가 커피 전메뉴 1+1"


class Command(BaseCommand):
    help = (
        "모든 쿠폰 중 benefit_snapshot.title 에 포함된 특정 문자열을 다른 문자열로 치환합니다.\n"
        "기본값: '커피 전메뉴 1+1' → '커피명가 커피 전메뉴 1+1'"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--old-text",
            dest="old_text",
            default=DEFAULT_OLD_TEXT,
            help="치환할 기존 문자열 (기본: '커피 전메뉴 1+1')",
        )
        parser.add_argument(
            "--new-text",
            dest="new_text",
            default=DEFAULT_NEW_TEXT,
            help="새 문자열 (기본: '커피명가 커피 전메뉴 1+1')",
        )
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
        old_text: str = options["old_text"]
        new_text: str = options["new_text"]
        dry_run = options["dry_run"]
        no_input = options["no_input"]

        alias = router.db_for_write(Coupon)

        # benefit_snapshot JSON 전체에 old_text 가 포함된 쿠폰 찾기
        qs = Coupon.objects.using(alias).filter(benefit_snapshot__icontains=old_text)

        total_count = qs.count()
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"benefit_snapshot 내에 '{old_text}' 이(가) 포함된 쿠폰이 없습니다."
                )
            )
            return

        self.stdout.write("\n=== benefit_snapshot title 문자열 치환 대상 ===")
        self.stdout.write(f"검색 문자열: '{old_text}' → '{new_text}'")
        self.stdout.write(f"총 후보 쿠폰 수 (benefit_snapshot 에 포함): {total_count}개\n")

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

        # 실제로 title 이 old_text 와 "완전히 동일한" 경우만 세부 필터링
        # (이미 '커피명가 커피 전메뉴 1+1' 처럼 prefix 가 붙은 건 건드리지 않기 위함)
        target_ids: list[int] = []
        for coupon in qs.iterator(chunk_size=1000):
            snap = coupon.benefit_snapshot or {}
            title = snap.get("title")
            if isinstance(title, str) and title == old_text:
                target_ids.append(coupon.id)

        if not target_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    f"benefit_snapshot.title 에 '{old_text}' 이(가 포함된 쿠폰은 없습니다."
                )
            )
            return

        self.stdout.write(
            f"\n실제 title 치환 대상 쿠폰 수 (benefit_snapshot.title 에 포함): {len(target_ids)}개"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 수정하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  위 {len(target_ids)}개의 쿠폰 benefit_snapshot.title 에서 "
                    f"'{old_text}' 를 '{new_text}' 로 치환합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nbenefit_snapshot.title 치환 중...")

        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in Coupon.objects.using(alias).filter(id__in=target_ids).iterator(
                chunk_size=500
            ):
                snap = coupon.benefit_snapshot or {}
                title = snap.get("title")
                if not isinstance(title, str) or title != old_text:
                    continue
                snap["title"] = new_text
                coupon.benefit_snapshot = snap
                coupon.save(update_fields=["benefit_snapshot"], using=alias)
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\n=== 업데이트 완료 ===\n"
                f"업데이트된 쿠폰 수: {updated_count}개\n"
                f"치환 문자열: '{old_text}' → '{new_text}'"
            )
        )


