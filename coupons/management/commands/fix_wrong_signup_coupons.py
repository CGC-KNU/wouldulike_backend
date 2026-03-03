"""
제휴 해제(is_affiliate=False) 식당에 잘못 발급된 신규가입/친구초대 쿠폰을
삭제하고, 해당 사용자에게 유효한 제휴 식당의 신규가입 쿠폰을 재발급합니다.

사용 예:
  python manage.py fix_wrong_signup_coupons --dry-run   # 미리보기
  python manage.py fix_wrong_signup_coupons             # 실행 (확인 필요)
  python manage.py fix_wrong_signup_coupons --no-input  # 확인 없이 실행
"""
from django.core.management.base import BaseCommand
from django.db import router
from django.contrib.auth import get_user_model

from restaurants.models import AffiliateRestaurant
from coupons.models import Coupon
from coupons.service import issue_signup_coupon

User = get_user_model()


class Command(BaseCommand):
    help = (
        "제휴 해제 식당에 잘못 발급된 쿠폰을 삭제하고, "
        "해당 사용자에게 유효한 신규가입 쿠폰을 재발급합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 변경 없이 대상만 출력",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 없이 바로 실행",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]

        read_alias = router.db_for_read(Coupon)
        write_alias = router.db_for_write(Coupon)
        ar_alias = router.db_for_read(AffiliateRestaurant)

        # 1) 제휴 해제 식당 ID 목록
        unaffiliated_ids = set(
            AffiliateRestaurant.objects.using(ar_alias)
            .filter(is_affiliate=False)
            .values_list("restaurant_id", flat=True)
        )
        if not unaffiliated_ids:
            self.stdout.write("제휴 해제 식당이 없습니다.")
            return

        # 2) 해당 식당에 발급된 신규가입/친구초대 쿠폰 조회
        from django.db.models import Q

        wrong_coupons = list(
            Coupon.objects.using(read_alias)
            .filter(restaurant_id__in=unaffiliated_ids)
            .filter(
                Q(issue_key__startswith="SIGNUP:")
                | Q(issue_key__startswith="REFERRAL_REFERRER:")
                | Q(issue_key__startswith="REFERRAL_REFEREE:")
            )
            .order_by("user_id", "id")
        )

        # 잘못된 SIGNUP 쿠폰이 있는 사용자만 재발급 대상 (REFERRAL만 잘못된 경우는 삭제만)
        users_needing_signup = set(
            c.user_id for c in wrong_coupons if c.issue_key.startswith("SIGNUP:")
        )
        user_ids = sorted(set(c.user_id for c in wrong_coupons))

        if not user_ids:
            self.stdout.write(self.style.SUCCESS("수정할 대상이 없습니다."))
            return

        self.stdout.write(f"\n제휴 해제 식당: {len(unaffiliated_ids)}개")
        self.stdout.write(f"잘못 발급된 쿠폰: {len(wrong_coupons)}개")
        self.stdout.write(f"영향받은 사용자: {len(user_ids)}명 (삭제)")
        self.stdout.write(f"신규가입 쿠폰 재발급 대상: {len(users_needing_signup)}명")
        self.stdout.write(f"user_id: {user_ids}\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] 실제 변경 없이 종료합니다."))
            return

        if not no_input:
            confirm = input("위 사용자들에게 잘못된 쿠폰 삭제 후 신규가입 쿠폰을 재발급합니다. 계속하시겠습니까? (yes/no): ")
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소되었습니다.")
                return

        # 3) 각 사용자별 처리
        success_count = 0
        fail_count = 0

        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  user_id={user_id}: 사용자 없음, 건너뜀"))
                fail_count += 1
                continue

            to_delete = [c for c in wrong_coupons if c.user_id == user_id]
            to_delete_ids = [c.id for c in to_delete]

            # 재발급 먼저 수행 → 삭제 (삭제 후 재발급 실패 시 쿠폰 없음 방지)
            if user_id in users_needing_signup:
                try:
                    issued = issue_signup_coupon(user)
                    if issued:
                        rid = issued[0].restaurant_id
                        deleted, _ = Coupon.objects.using(write_alias).filter(
                            id__in=to_delete_ids
                        ).delete()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  user_id={user_id}: 재발급 완료 (restaurant_id={rid}), 삭제 {deleted}개"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  user_id={user_id}: 재발급 실패 (대상 식당 없음), 삭제하지 않음"
                            )
                        )
                        fail_count += 1
                        continue
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  user_id={user_id}: 재발급 오류 - {e}")
                    )
                    fail_count += 1
                    continue
            else:
                # REFERRAL만 잘못된 경우: 삭제만
                deleted, _ = Coupon.objects.using(write_alias).filter(
                    id__in=to_delete_ids
                ).delete()
                self.stdout.write(
                    self.style.SUCCESS(f"  user_id={user_id}: 삭제 {deleted}개 (재발급 불필요)")
                )

            success_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"완료: 성공 {success_count}명, 실패 {fail_count}명")
        )
