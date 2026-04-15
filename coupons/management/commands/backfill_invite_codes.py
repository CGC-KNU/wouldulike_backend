"""
InviteCode가 없는 사용자에게 기본 추천코드( campaign_code=None )를 일괄 생성합니다.

배경:
- User는 default DB에, InviteCode는 cloudsql(coupons DB)에 저장되는 멀티 DB 구조입니다.
- 과거 배포/마이그레이션 순서/환경변수에 따라 InviteCode가 누락된 사용자가 있을 수 있어
  추천코드 입력 시 `invalid referral code`가 발생합니다.

사용 예:
  python manage.py backfill_invite_codes --dry-run
  python manage.py backfill_invite_codes --limit 100
  python manage.py backfill_invite_codes --no-input
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import router

from coupons.models import InviteCode
from coupons.service import ensure_invite_code


User = get_user_model()


class Command(BaseCommand):
    help = "InviteCode가 누락된 사용자에게 기본 추천코드 생성"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="대상만 출력하고 종료")
        parser.add_argument("--no-input", action="store_true", help="확인 없이 바로 실행")
        parser.add_argument("--limit", type=int, default=None, help="최대 N명만 처리(테스트용)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]
        limit = options.get("limit")

        invite_alias = router.db_for_read(InviteCode)

        # cloudsql에 기본 invite code(campaign_code is null)를 가진 user_id 목록
        existing_user_ids = set(
            InviteCode.objects.using(invite_alias)
            .filter(campaign_code__isnull=True)
            .values_list("user_id", flat=True)
            .distinct()
        )

        qs = User.objects.using("default").exclude(id__in=existing_user_ids).order_by("id")
        if limit:
            qs = qs[:limit]

        targets = list(qs.values_list("id", "kakao_id"))
        if not targets:
            self.stdout.write(self.style.SUCCESS("대상 없음 (모든 사용자에게 InviteCode 존재)"))
            return

        self.stdout.write(f"InviteCode 누락 사용자: {len(targets)}명")
        for uid, kid in targets[:20]:
            self.stdout.write(f"  user_id={uid}, kakao_id={kid or '-'}")
        if len(targets) > 20:
            self.stdout.write(f"  ... 외 {len(targets) - 20}명")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] 실제 생성 없이 종료합니다."))
            return

        if not no_input:
            confirm = input(f"위 {len(targets)}명에 대해 InviteCode를 생성합니다. 계속? (yes/no): ")
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소되었습니다.")
                return

        ok = 0
        fail = 0
        for uid, _kid in targets:
            try:
                user = User.objects.using("default").get(id=uid)
                ic = ensure_invite_code(user)
                # ensure_invite_code는 라우터에 의해 cloudsql에 저장되어야 함
                self.stdout.write(self.style.SUCCESS(f"  user_id={uid}: {ic.code}"))
                ok += 1
            except Exception as exc:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"  user_id={uid}: 실패 - {exc}"))
                fail += 1

        self.stdout.write(self.style.SUCCESS(f"완료: 성공 {ok}명, 실패 {fail}명"))

