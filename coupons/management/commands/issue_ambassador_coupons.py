"""
엠버서더 보상을 위해 특정 카카오 ID 사용자에게 전체 제휴식당 쿠폰을 발급하는 명령어
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from coupons.service import issue_ambassador_coupons

User = get_user_model()


class Command(BaseCommand):
    help = "엠버서더 보상을 위해 특정 카카오 ID 사용자에게 전체 제휴식당 쿠폰을 발급합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-id",
            type=int,
            required=True,
            help="쿠폰을 발급받을 사용자의 카카오 ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 발급하지 않고 미리보기만 표시",
        )

    def handle(self, *args, **options):
        kakao_id = options["kakao_id"]
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY-RUN 모드: 실제 발급 없음 ===\n"))

        # 사용자 조회
        try:
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            raise CommandError(f"카카오 ID {kakao_id}에 해당하는 사용자를 찾을 수 없습니다.")

        self.stdout.write(f"사용자 정보:")
        self.stdout.write(f"  - User ID: {user.id}")
        self.stdout.write(f"  - Kakao ID: {user.kakao_id}")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DRY-RUN] 카카오 ID {kakao_id} 사용자에게 전체 제휴식당 쿠폰을 발급할 예정입니다."
                )
            )
            return

        # 쿠폰 발급
        try:
            result = issue_ambassador_coupons(user)
            coupons = result["coupons"]
            total_issued = result["total_issued"]
            failed_restaurants = result["failed_restaurants"]

            self.stdout.write(self.style.SUCCESS(f"\n쿠폰 발급 완료!"))
            self.stdout.write(f"  - 총 발급된 쿠폰 수: {total_issued}개")
            self.stdout.write("")

            if coupons:
                self.stdout.write("발급된 쿠폰 목록 (처음 10개):")
                for coupon in coupons[:10]:
                    restaurant_name = (
                        coupon.benefit_snapshot.get("restaurant_name", "N/A")
                        if coupon.benefit_snapshot
                        else "N/A"
                    )
                    self.stdout.write(
                        f"  - 쿠폰 코드: {coupon.code}, "
                        f"식당 ID: {coupon.restaurant_id}, "
                        f"식당명: {restaurant_name}"
                    )
                if len(coupons) > 10:
                    self.stdout.write(f"  ... 외 {len(coupons) - 10}개 더 있습니다.")

            if failed_restaurants:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(f"발급 실패한 식당 수: {len(failed_restaurants)}개")
                )
                for restaurant_id, error in failed_restaurants[:5]:
                    self.stdout.write(f"  - 식당 ID {restaurant_id}: {error}")
                if len(failed_restaurants) > 5:
                    self.stdout.write(f"  ... 외 {len(failed_restaurants) - 5}개 더 있습니다.")

        except Exception as exc:
            raise CommandError(f"쿠폰 발급 중 오류 발생: {str(exc)}") from exc

