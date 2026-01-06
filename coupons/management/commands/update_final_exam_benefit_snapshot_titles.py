from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import Coupon, CouponType, Campaign


OLD_TITLE = "커피 전메뉴 1+1"
NEW_TITLE = "커피명가 커피 전메뉴 1+1"


class Command(BaseCommand):
    help = (
        "기말고사 이벤트(FINAL_EXAM_SPECIAL / FINAL_EXAM_EVENT)로 발급된 쿠폰 중 "
        f"benefit_snapshot.title 이 '{OLD_TITLE}' 인 쿠폰을 '{NEW_TITLE}' 로 수정합니다."
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

        try:
            final_exam_ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
            final_exam_camp = Campaign.objects.using(alias).get(
                code="FINAL_EXAM_EVENT", active=True
            )
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_SPECIAL 쿠폰 타입을 찾을 수 없습니다."))
            return
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_EVENT 캠페인을 찾을 수 없습니다."))
            return

        coupons = Coupon.objects.using(alias).filter(
            coupon_type=final_exam_ct,
            campaign=final_exam_camp,
            benefit_snapshot__title=OLD_TITLE,
        )

        total_count = coupons.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"benefit_snapshot.title 이 '{OLD_TITLE}' 인 기말고사 쿠폰이 없습니다."
                )
            )
            return

        self.stdout.write("\n=== 기말고사 쿠폰 benefit_snapshot.title 수정 대상 ===")
        self.stdout.write(f"총 대상 쿠폰 수: {total_count}개\n")

        status_counts = (
            coupons.values("status")
            .order_by("status")
            .annotate(count=__import__("django.db.models", fromlist=["Count"]).Count("id"))
        )
        self.stdout.write("상태별 분포:")
        for item in status_counts:
            self.stdout.write(f"  {item['status']}: {item['count']}개")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 수정하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  위 {total_count}개의 쿠폰 benefit_snapshot.title 을 "
                    f"'{OLD_TITLE}' 에서 '{NEW_TITLE}' 로 수정합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nbenefit_snapshot.title 업데이트 중...")

        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in coupons.iterator(chunk_size=500):
                snapshot = coupon.benefit_snapshot or {}
                if snapshot.get("title") != OLD_TITLE:
                    continue
                snapshot["title"] = NEW_TITLE
                coupon.benefit_snapshot = snapshot
                coupon.save(update_fields=["benefit_snapshot"], using=alias)
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\n=== 업데이트 완료 ===\n"
                f"업데이트된 쿠폰 수: {updated_count}개\n"
                f"새 title: '{NEW_TITLE}'"
            )
        )



