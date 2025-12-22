from django.core.management.base import BaseCommand
from django.db import transaction, router

from coupons.models import CouponType, RestaurantCouponBenefit
from restaurants.models import AffiliateRestaurant


OLD_SUBTITLE = "커피 전메뉴 1+1"
NEW_SUBTITLE = "커피명가 커피 전메뉴 1+1"
LABO_KEYWORD = "라보"


class Command(BaseCommand):
    help = (
        "[라보] 기말고사 이벤트 단과대학 쿠폰의 RestaurantCouponBenefit.subtitle 을 "
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

        alias = router.db_for_write(RestaurantCouponBenefit)

        try:
            final_exam_ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_SPECIAL 쿠폰 타입을 찾을 수 없습니다."))
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

        benefits = (
            RestaurantCouponBenefit.objects.using(alias)
            .select_related("restaurant")
            .filter(
                coupon_type=final_exam_ct,
                restaurant_id__in=labo_ids,
                subtitle=OLD_SUBTITLE,
            )
        )

        total_count = benefits.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"'{LABO_KEYWORD}' 관련 FINAL_EXAM_SPECIAL 쿠폰 중 subtitle이 '{OLD_SUBTITLE}'인 항목이 없습니다."
                )
            )
            return

        self.stdout.write("\n=== [라보 기말고사 단과대학 쿠폰] subtitle 수정 대상 현황 ===")
        self.stdout.write(f"총 대상 RestaurantCouponBenefit 수: {total_count}개\n")

        sample = list(benefits[:20])
        if sample:
            self.stdout.write("예시 식당들:")
            for b in sample:
                name = getattr(b.restaurant, "name", None)
                self.stdout.write(f"  - restaurant_id={b.restaurant_id}, name={name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 수정하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  위 {total_count}개의 RestaurantCouponBenefit.subtitle 을 "
                    f"'{OLD_SUBTITLE}'에서 '{NEW_SUBTITLE}'로 수정합니다. 계속하시겠습니까?"
                )
            )
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write("\nsubtitle 업데이트 중...")
        with transaction.atomic(using=alias):
            updated_count = benefits.update(subtitle=NEW_SUBTITLE)

        self.stdout.write(
            self.style.SUCCESS(
                "\n=== 업데이트 완료 ===\n"
                f"업데이트된 RestaurantCouponBenefit: {updated_count}개\n"
                f"새 subtitle: '{NEW_SUBTITLE}'"
            )
        )



