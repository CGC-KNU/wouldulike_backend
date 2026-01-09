from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import Coupon, CouponType, Campaign
from restaurants.models import AffiliateRestaurant

from coupons.management.commands.update_labo_final_exam_benefits import (  # noqa: F401
    OLD_SUBTITLE,
    NEW_SUBTITLE,
    LABO_KEYWORD,
)


class Command(BaseCommand):
    help = (
        "[라보] 기말고사 이벤트 단과대학 쿠폰 중 이미 발급된 쿠폰의 benefit_snapshot.subtitle 을 "
        f"'{OLD_SUBTITLE}'에서 '{NEW_SUBTITLE}'로 수정합니다."
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

        # 라보 제휴 식당 restaurant_id 목록
        labo_ids = list(
            AffiliateRestaurant.objects.using(alias)
            .filter(name__icontains=LABO_KEYWORD)
            .values_list("restaurant_id", flat=True)
        )

        if not labo_ids:
            self.stdout.write(
                self.style.WARNING(f"이름에 '{LABO_KEYWORD}'가 포함된 제휴 식당을 찾을 수 없습니다.")
            )
            return

        coupons = Coupon.objects.using(alias).filter(
            coupon_type=final_exam_ct,
            campaign=final_exam_camp,
            restaurant_id__in=labo_ids,
            benefit_snapshot__subtitle=OLD_SUBTITLE,
        )

        total_count = coupons.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"라보 기말고사 쿠폰 중 benefit_snapshot.subtitle 이 '{OLD_SUBTITLE}'인 쿠폰이 없습니다."
                )
            )
            return

        self.stdout.write("\n=== [라보 기말고사 단과대학 쿠폰] benefit_snapshot.subtitle 수정 대상 ===")
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
                    f"\n⚠️  위 {total_count}개의 쿠폰 benefit_snapshot.subtitle 을 "
                    f"'{OLD_SUBTITLE}'에서 '{NEW_SUBTITLE}'로 수정합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nbenefit_snapshot.subtitle 업데이트 중...")

        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in coupons.iterator(chunk_size=500):
                snapshot = coupon.benefit_snapshot or {}
                subtitle = snapshot.get("subtitle")
                if subtitle != OLD_SUBTITLE:
                    continue
                snapshot["subtitle"] = NEW_SUBTITLE
                coupon.benefit_snapshot = snapshot
                coupon.save(update_fields=["benefit_snapshot"], using=alias)
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\n=== 업데이트 완료 ===\n"
                f"업데이트된 쿠폰 수: {updated_count}개\n"
                f"새 subtitle: '{NEW_SUBTITLE}'"
            )
        )







