"""
삭제된 팀스 쿠치나 사용자 8명을 복구하고, 유효한 신규가입 쿠폰을 발급합니다.

앱 수정 없이 해결: 같은 user_id로 복구하면 기존 JWT가 그대로 동작하고,
쿠폰 API 호출 시 새로 발급한 쿠폰이 반환됩니다.

사용 예:
  python manage.py restore_teamscoochina_users --dry-run
  python manage.py restore_teamscoochina_users
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth import get_user_model
from coupons.models import Coupon
from coupons.service import ensure_invite_code, issue_signup_coupon
from django.db import router

User = get_user_model()

# 삭제된 팀스 쿠치나 사용자 (user_id, kakao_id)
TEAMSCOOCHINA_USERS = [
    (668, 4635426842),
    (669, 4563106425),
    (670, 4777914095),
    (671, 4777915441),
    (672, 4777975557),
    (673, 4777988820),
    (674, 4778038553),
    (675, 4778040563),
]


class Command(BaseCommand):
    help = "삭제된 팀스 쿠치나 사용자 8명 복구 + 신규가입 쿠폰 발급"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 변경 없이 대상만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write(f"\n복구 대상: {len(TEAMSCOOCHINA_USERS)}명")
        for uid, kid in TEAMSCOOCHINA_USERS:
            self.stdout.write(f"  user_id={uid}, kakao_id={kid}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제 변경 없이 종료합니다."))
            return

        confirm = input("\n위 사용자들을 복구하고 신규가입 쿠폰을 발급합니다. 계속하시겠습니까? (yes/no): ")
        if confirm.strip().lower() != "yes":
            self.stdout.write("취소되었습니다.")
            return

        success = 0
        fail = 0

        for user_id, kakao_id in TEAMSCOOCHINA_USERS:
            try:
                # 1) User가 이미 존재하는지 확인
                user = User.objects.filter(id=user_id).first()
                if user:
                    # 기존 SIGNUP 쿠폰이 있으면 스킵 (이미 복구된 경우)
                    alias = router.db_for_read(Coupon)
                    has_signup = Coupon.objects.using(alias).filter(
                        user_id=user_id,
                        issue_key__startswith="SIGNUP:",
                    ).exists()
                    if has_signup:
                        self.stdout.write(self.style.SUCCESS(f"  user_id={user_id}: 이미 복구됨, 스킵"))
                        success += 1
                        continue
                else:
                    # 2) User 복구 (같은 id로 INSERT - JWT 호환)
                    # unusable password = "!" (Django AbstractBaseUser 형식)
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO accounts_user (id, username, kakao_id, password, is_active, is_staff, is_superuser)
                            VALUES (%s, %s, %s, %s, true, false, false)
                            """,
                            [user_id, str(kakao_id), kakao_id, "!"],
                        )
                    user = User.objects.get(id=user_id)

                # 3) InviteCode 생성
                ensure_invite_code(user)

                # 4) 신규가입 쿠폰 발급
                issued = issue_signup_coupon(user)
                if issued:
                    rid = issued[0].restaurant_id
                    self.stdout.write(
                        self.style.SUCCESS(f"  user_id={user_id}: 복구 완료, 쿠폰 발급 (restaurant_id={rid})")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  user_id={user_id}: 복구 완료, 쿠폰 발급 실패 (대상 식당 없음)")
                    )
                    fail += 1
                    continue

                success += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  user_id={user_id}: 오류 - {e}"))
                fail += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"완료: 성공 {success}명, 실패 {fail}명"))
