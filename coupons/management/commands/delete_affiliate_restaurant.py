from django.core.management.base import BaseCommand, CommandError
from django.db import router

from restaurants.models import AffiliateRestaurant
from coupons.models import Coupon, MerchantPin, RestaurantCouponBenefit


class Command(BaseCommand):
    help = (
        "특정 restaurant_id 에 해당하는 제휴 식당(AffiliateRestaurant)과 "
        "연결된 PIN(MerchantPin), 식당별 쿠폰 혜택(RestaurantCouponBenefit)을 삭제합니다.\n"
        "쿠폰(Coupon)과 스탬프(StampWallet/StampEvent) 기록은 보존합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            required=True,
            help="삭제할 제휴 식당의 restaurant_id",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 삭제하지 않고, 어떤 데이터가 삭제 대상인지 요약만 출력합니다.",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 프롬프트 없이 바로 실행합니다.",
        )

    def handle(self, *args, **options):
        restaurant_id: int = options["restaurant_id"]
        dry_run: bool = options["dry_run"]
        no_input: bool = options["no_input"]

        coupon_alias = router.db_for_write(Coupon)
        restaurant_alias = router.db_for_write(AffiliateRestaurant)

        # 대상 제휴 식당 존재 여부 확인
        affiliate = (
            AffiliateRestaurant.objects.using(restaurant_alias)
            .filter(restaurant_id=restaurant_id)
            .first()
        )

        if not affiliate:
            self.stdout.write(
                self.style.WARNING(
                    f"restaurants_affiliate 에 restaurant_id={restaurant_id} 제휴 식당이 존재하지 않습니다."
                )
            )

        # 연관 객체 수집
        pin_qs = MerchantPin.objects.using(coupon_alias).filter(restaurant_id=restaurant_id)
        benefit_qs = RestaurantCouponBenefit.objects.using(coupon_alias).filter(
            restaurant_id=restaurant_id
        )
        coupon_count = (
            Coupon.objects.using(coupon_alias)
            .filter(restaurant_id=restaurant_id)
            .count()
        )

        pin_count = pin_qs.count()
        benefit_count = benefit_qs.count()

        self.stdout.write(
            f"삭제 대상 요약 (restaurant_id={restaurant_id}):\n"
            f" - AffiliateRestaurant: {'1개' if affiliate else '0개(없음)'}\n"
            f" - MerchantPin: {pin_count}개\n"
            f" - RestaurantCouponBenefit: {benefit_count}개\n"
            f" - Coupon (보존): {coupon_count}개\n"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] 실제로는 아무 데이터도 삭제되지 않습니다."))
            return

        if not no_input:
            confirm = input(
                f'restaurant_id={restaurant_id} 에 대한 제휴 식당/핀/쿠폰혜택을 삭제합니다. '
                f'쿠폰/스탬프 기록은 남겨둡니다.\n'
                f'계속하려면 "yes" 를 입력하세요: '
            )
            if confirm.lower() != "yes":
                raise CommandError("작업이 취소되었습니다.")

        # 실제 삭제 수행
        deleted_affiliate = deleted_pins = deleted_benefits = 0

        if affiliate:
            deleted_affiliate, _ = (
                AffiliateRestaurant.objects.using(restaurant_alias)
                .filter(restaurant_id=restaurant_id)
                .delete()
            )

        if pin_count:
            deleted_pins, _ = pin_qs.delete()

        if benefit_count:
            deleted_benefits, _ = benefit_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"삭제 완료 (restaurant_id={restaurant_id}) - "
                f"AffiliateRestaurant: {deleted_affiliate}개, "
                f"MerchantPin: {deleted_pins}개, "
                f"RestaurantCouponBenefit: {deleted_benefits}개. "
                f"쿠폰(Coupon)과 스탬프 기록은 그대로 유지했습니다."
            )
        )


