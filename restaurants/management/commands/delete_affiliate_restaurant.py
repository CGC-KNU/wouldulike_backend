"""
제휴식당 삭제 명령어
제휴식당과 관련된 모든 데이터(쿠폰, 스탬프, PIN 등)를 삭제합니다.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, router, transaction
from django.db.models import Count

from restaurants.models import AffiliateRestaurant
from coupons.models import (
    Coupon,
    RestaurantCouponBenefit,
    MerchantPin,
    StampWallet,
    StampEvent,
)


class Command(BaseCommand):
    help = "제휴식당을 삭제하고 관련된 모든 데이터(쿠폰, 스탬프, PIN 등)를 정리합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            required=True,
            help="삭제할 제휴식당의 restaurant_id",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 삭제하지 않고 미리보기만 표시",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 프롬프트 없이 바로 실행",
        )
        parser.add_argument(
            "--delete-coupons",
            action="store_true",
            help="해당 식당의 쿠폰도 함께 삭제 (기본값: False, 쿠폰은 유지)",
        )
        parser.add_argument(
            "--delete-stamps",
            action="store_true",
            help="해당 식당의 스탬프 지갑/이벤트도 함께 삭제 (기본값: False, 스탬프는 유지)",
        )

    def handle(self, *args, **options):
        restaurant_id = options["restaurant_id"]
        dry_run = options["dry_run"]
        no_input = options["no_input"]
        delete_coupons = options["delete_coupons"]
        delete_stamps = options["delete_stamps"]

        # 제휴식당 조회
        alias = router.db_for_read(AffiliateRestaurant)
        restaurant = AffiliateRestaurant.objects.using(alias).filter(
            restaurant_id=restaurant_id
        ).first()

        if not restaurant:
            # CloudSQL에서도 확인
            try:
                restaurant = AffiliateRestaurant.objects.using("cloudsql").filter(
                    restaurant_id=restaurant_id
                ).first()
                alias = "cloudsql"
            except Exception:
                pass

        if not restaurant:
            raise CommandError(
                f"restaurant_id={restaurant_id} 에 해당하는 제휴식당을 찾을 수 없습니다."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n제휴식당 정보:\n"
                f"  ID: {restaurant.restaurant_id}\n"
                f"  이름: {restaurant.name}\n"
                f"  설명: {restaurant.description or '(없음)'}"
            )
        )

        # 관련 데이터 조회
        coupon_db = router.db_for_read(Coupon)
        
        # RestaurantCouponBenefit 개수
        benefit_count = RestaurantCouponBenefit.objects.using(coupon_db).filter(
            restaurant_id=restaurant_id
        ).count()

        # MerchantPin 존재 여부
        pin_exists = MerchantPin.objects.using(coupon_db).filter(
            restaurant_id=restaurant_id
        ).exists()

        # Coupon 개수
        coupon_count = Coupon.objects.using(coupon_db).filter(
            restaurant_id=restaurant_id
        ).count()

        # StampWallet 개수
        wallet_count = StampWallet.objects.using(coupon_db).filter(
            restaurant_id=restaurant_id
        ).count()

        # StampEvent 개수
        event_count = StampEvent.objects.using(coupon_db).filter(
            restaurant_id=restaurant_id
        ).count()

        self.stdout.write(
            f"\n관련 데이터 현황:\n"
            f"  RestaurantCouponBenefit: {benefit_count}개\n"
            f"  MerchantPin: {'있음' if pin_exists else '없음'}\n"
            f"  Coupon: {coupon_count}개\n"
            f"  StampWallet: {wallet_count}개\n"
            f"  StampEvent: {event_count}개"
        )

        # 삭제 계획 표시
        deletions = []
        deletions.append(f"  - RestaurantCouponBenefit: {benefit_count}개 (자동 삭제)")
        deletions.append(f"  - MerchantPin: {'1개' if pin_exists else '0개'} (자동 삭제)")

        if delete_coupons:
            deletions.append(f"  - Coupon: {coupon_count}개")
        else:
            deletions.append(f"  - Coupon: {coupon_count}개 (유지, restaurant_id는 NULL로 설정)")

        if delete_stamps:
            deletions.append(f"  - StampWallet: {wallet_count}개")
            deletions.append(f"  - StampEvent: {event_count}개")
        else:
            deletions.append(f"  - StampWallet: {wallet_count}개 (유지)")
            deletions.append(f"  - StampEvent: {event_count}개 (유지)")

        deletions.append(f"  - AffiliateRestaurant: 1개")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 다음 항목들이 삭제될 예정입니다:"))
            for item in deletions:
                self.stdout.write(item)
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제로 DB는 변경되지 않았습니다."))
            return

        # 확인 프롬프트
        if not no_input:
            self.stdout.write(self.style.WARNING("\n⚠️  다음 항목들이 삭제됩니다:"))
            for item in deletions:
                self.stdout.write(item)
            confirm = input('\n계속하려면 "yes"를 입력하세요: ')
            if confirm.lower() != "yes":
                raise CommandError("작업이 취소되었습니다.")

        # 실제 삭제 수행
        self.stdout.write("\n삭제 작업 시작...")

        with transaction.atomic(using=coupon_db):
            # 1. RestaurantCouponBenefit 삭제 (CASCADE로 자동 삭제되지만 명시적으로)
            deleted_benefits = RestaurantCouponBenefit.objects.using(coupon_db).filter(
                restaurant_id=restaurant_id
            ).delete()[0]
            self.stdout.write(f"  ✓ RestaurantCouponBenefit 삭제: {deleted_benefits}개")

            # 2. MerchantPin 삭제 (CASCADE로 자동 삭제되지만 명시적으로)
            deleted_pins = MerchantPin.objects.using(coupon_db).filter(
                restaurant_id=restaurant_id
            ).delete()[0]
            self.stdout.write(f"  ✓ MerchantPin 삭제: {deleted_pins}개")

            # 3. Coupon 처리
            if delete_coupons:
                deleted_coupons = Coupon.objects.using(coupon_db).filter(
                    restaurant_id=restaurant_id
                ).delete()[0]
                self.stdout.write(f"  ✓ Coupon 삭제: {deleted_coupons}개")
            else:
                updated_coupons = Coupon.objects.using(coupon_db).filter(
                    restaurant_id=restaurant_id
                ).update(restaurant_id=None)
                self.stdout.write(f"  ✓ Coupon restaurant_id NULL 설정: {updated_coupons}개")

            # 4. StampWallet 처리
            if delete_stamps:
                deleted_wallets = StampWallet.objects.using(coupon_db).filter(
                    restaurant_id=restaurant_id
                ).delete()[0]
                self.stdout.write(f"  ✓ StampWallet 삭제: {deleted_wallets}개")
            else:
                self.stdout.write(f"  - StampWallet 유지: {wallet_count}개")

            # 5. StampEvent 처리
            if delete_stamps:
                deleted_events = StampEvent.objects.using(coupon_db).filter(
                    restaurant_id=restaurant_id
                ).delete()[0]
                self.stdout.write(f"  ✓ StampEvent 삭제: {deleted_events}개")
            else:
                self.stdout.write(f"  - StampEvent 유지: {event_count}개")

        # 6. AffiliateRestaurant 삭제 (raw SQL 사용, managed=False이므로)
        write_alias = router.db_for_write(AffiliateRestaurant)
        with connections[write_alias].cursor() as cursor:
            cursor.execute(
                "DELETE FROM restaurants_affiliate WHERE restaurant_id = %s",
                [restaurant_id],
            )
            if cursor.rowcount == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚠️  restaurants_affiliate에서 restaurant_id={restaurant_id}를 찾을 수 없습니다."
                    )
                )
            else:
                self.stdout.write(f"  ✓ AffiliateRestaurant 삭제: 1개")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ 제휴식당 삭제 완료: restaurant_id={restaurant_id}, name='{restaurant.name}'"
            )
        )

