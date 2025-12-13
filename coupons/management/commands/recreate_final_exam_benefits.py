from django.core.management.base import BaseCommand
from coupons.models import CouponType, RestaurantCouponBenefit


class Command(BaseCommand):
    help = "FINAL_EXAM_SPECIAL 쿠폰 타입의 RestaurantCouponBenefit를 삭제하고 새로 등록합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 변경하지 않고 변경될 내용만 출력합니다.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        try:
            referral_type = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
            final_exam_type = CouponType.objects.get(code="FINAL_EXAM_SPECIAL")
        except CouponType.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"쿠폰 타입을 찾을 수 없습니다: {e}"))
            return

        # 기존 FINAL_EXAM_SPECIAL의 RestaurantCouponBenefit 삭제
        existing_benefits = RestaurantCouponBenefit.objects.filter(coupon_type=final_exam_type)
        deleted_count = existing_benefits.count()

        if not dry_run:
            existing_benefits.delete()
            self.stdout.write(
                self.style.SUCCESS(f"기존 RestaurantCouponBenefit {deleted_count}개를 삭제했습니다.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"기존 RestaurantCouponBenefit {deleted_count}개를 삭제할 예정입니다.")
            )

        # REFERRAL_BONUS_REFEREE의 식당별 쿠폰 내용 가져오기
        referral_benefits = RestaurantCouponBenefit.objects.filter(
            coupon_type=referral_type, active=True
        )

        # 각 식당별 쿠폰 내용을 FINAL_EXAM_SPECIAL로 새로 등록
        # title은 REFERRAL_BONUS_REFEREE의 title을 그대로 사용 (쿠폰 보상 내역)
        # subtitle은 "기말고사 쪽지 이벤트"로 설정
        # benefit_json은 REFERRAL_BONUS_REFEREE와 동일하게 유지
        created_count = 0
        for benefit in referral_benefits:
            if dry_run:
                self.stdout.write(
                    f"생성 예정: restaurant_id={benefit.restaurant_id}, "
                    f"title='{benefit.title}', subtitle='기말고사 쪽지 이벤트'"
                )
            else:
                RestaurantCouponBenefit.objects.create(
                    coupon_type=final_exam_type,
                    restaurant_id=benefit.restaurant_id,
                    title=benefit.title,  # 쿠폰 보상 내역 (REFERRAL_BONUS_REFEREE와 동일)
                    subtitle="기말고사 쪽지 이벤트",  # 이벤트 이름
                    benefit_json=benefit.benefit_json,
                    active=benefit.active,
                )
            created_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"총 {created_count}개의 RestaurantCouponBenefit를 생성할 예정입니다.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"총 {created_count}개의 RestaurantCouponBenefit를 생성했습니다.")
            )

