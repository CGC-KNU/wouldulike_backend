"""
여러 카카오 ID 사용자에게 일괄 쿠폰 발급하는 명령어
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from coupons.service import issue_ambassador_coupons

User = get_user_model()


class Command(BaseCommand):
    help = "여러 카카오 ID 사용자에게 일괄 쿠폰을 발급합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--kakao-ids",
            type=str,
            required=True,
            help="쿠폰을 발급받을 사용자들의 카카오 ID (쉼표로 구분)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 발급하지 않고 미리보기만 표시",
        )

    def handle(self, *args, **options):
        kakao_ids_str = options["kakao_ids"]
        dry_run = options.get("dry_run", False)

        # 쉼표로 구분된 카카오 ID 파싱
        try:
            kakao_ids = [int(kid.strip()) for kid in kakao_ids_str.split(",") if kid.strip()]
        except ValueError as e:
            raise CommandError(f"카카오 ID 형식이 올바르지 않습니다: {e}")

        if not kakao_ids:
            raise CommandError("카카오 ID가 제공되지 않았습니다.")

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY-RUN 모드: 실제 발급 없음 ===\n"))

        self.stdout.write(f"총 {len(kakao_ids)}명의 사용자에게 쿠폰을 발급합니다.\n")
        self.stdout.write("=" * 80 + "\n")

        success_count = 0
        failed_count = 0
        failed_users = []

        for idx, kakao_id in enumerate(kakao_ids, 1):
            self.stdout.write(f"\n[{idx}/{len(kakao_ids)}] 카카오 ID: {kakao_id}")

            # 사용자 조회
            try:
                user = User.objects.get(kakao_id=kakao_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ 사용자를 찾을 수 없습니다.")
                )
                failed_count += 1
                failed_users.append((kakao_id, "사용자를 찾을 수 없음"))
                continue

            self.stdout.write(f"  - User ID: {user.id}")
            self.stdout.write(f"  - Kakao ID: {user.kakao_id}")

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [DRY-RUN] 쿠폰 발급 예정"
                    )
                )
                success_count += 1
                continue

            # 쿠폰 발급
            try:
                result = issue_ambassador_coupons(user)
                total_issued = result["total_issued"]
                failed_restaurants = result.get("failed_restaurants", [])

                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ 쿠폰 발급 완료: {total_issued}개")
                )
                if failed_restaurants:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  발급 실패한 식당: {len(failed_restaurants)}개")
                    )
                success_count += 1

            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ 쿠폰 발급 실패: {str(exc)}")
                )
                failed_count += 1
                failed_users.append((kakao_id, str(exc)))

        # 최종 결과 요약
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\n✅ 성공: {success_count}명"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ 실패: {failed_count}명"))
            self.stdout.write("\n실패한 사용자:")
            for kakao_id, error in failed_users:
                self.stdout.write(f"  - 카카오 ID {kakao_id}: {error}")
        self.stdout.write("=" * 80 + "\n")

