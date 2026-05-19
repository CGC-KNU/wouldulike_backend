"""
아동학부 쿠폰팩 일괄 발급 (술집·주점 풀 1+3+5종, subtitle [아동학부 쿠폰팩 🐣]).

사용 예:
  python manage.py ensure_child_dept_event
  python manage.py issue_child_dept_coupon_pack --dry-run
  python manage.py issue_child_dept_coupon_pack --no-input
  python manage.py issue_child_dept_coupon_pack --excel "/path/to/신청폼.xlsx" --no-input
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from coupons.child_dept_event import (
    CHILD_DEPT_DEFAULT_NICKNAMES,
    CHILD_DEPT_SUBTITLE,
    ensure_child_dept_event_data,
    load_nicknames_from_excel,
    merge_nickname_lists,
)
from coupons.child_dept_event import CHILD_DEPT_PACK_TIER_COUNTS
from coupons.festival_jungdunbam import resolve_cloudsql_alias
from coupons.service import issue_child_dept_coupon_pack_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "아동학부 신청 닉네임(+추가 닉네임)에게 쿠폰팩 9장(1+3+5) 발급"

    def add_arguments(self, parser):
        parser.add_argument(
            "--excel",
            type=str,
            default=None,
            help="신청폼 xlsx 경로 (미지정 시 기본 닉네임 목록만 사용)",
        )
        parser.add_argument(
            "--nickname",
            action="append",
            default=[],
            help="추가 닉네임 (여러 번 지정 가능)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="발급 없이 대상만 출력",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="확인 없이 실행",
        )
        parser.add_argument(
            "--skip-ensure",
            action="store_true",
            help="ensure_child_dept_event_data 생략",
        )

    def handle(self, *args, **options):
        nick_lists: list[list[str]] = [list(CHILD_DEPT_DEFAULT_NICKNAMES)]
        if options.get("nickname"):
            nick_lists.append(options["nickname"])

        excel_path = options.get("excel")
        if excel_path:
            try:
                nick_lists.append(load_nicknames_from_excel(excel_path))
            except FileNotFoundError:
                raise CommandError(f"엑셀 파일 없음: {excel_path}")
            except Exception as exc:
                raise CommandError(f"엑셀 읽기 실패: {exc}") from exc

        nicknames = merge_nickname_lists(*nick_lists)
        if not nicknames:
            raise CommandError("발급 대상 닉네임이 없습니다.")

        if not options["skip_ensure"]:
            db = ensure_child_dept_event_data(db_alias=resolve_cloudsql_alias())
            self.stdout.write(self.style.SUCCESS(f"이벤트 데이터 반영 (db={db})"))

        per_user = sum(CHILD_DEPT_PACK_TIER_COUNTS.values())
        self.stdout.write(
            f"\n쿠폰팩: {CHILD_DEPT_SUBTITLE}\n"
            f"티어: {CHILD_DEPT_PACK_TIER_COUNTS} → 사용자당 최대 {per_user}장\n"
            f"대상 닉네임 {len(nicknames)}명:\n"
        )
        for nick in nicknames:
            self.stdout.write(f"  - {nick}")

        resolved: list[tuple[str, User]] = []
        missing: list[str] = []
        ambiguous: list[tuple[str, int]] = []

        user_alias = router.db_for_read(User)
        for nick in nicknames:
            matches = list(
                User.objects.using(user_alias)
                .filter(nickname__iexact=nick)
                .order_by("id")[:3]
            )
            if not matches:
                missing.append(nick)
            elif len(matches) > 1:
                ambiguous.append((nick, len(matches)))
            else:
                resolved.append((nick, matches[0]))

        self.stdout.write(f"\n매칭됨: {len(resolved)}명")
        if missing:
            self.stdout.write(self.style.WARNING(f"미가입/닉네임 불일치: {len(missing)}명"))
            for nick in missing:
                self.stdout.write(f"  ? {nick}")
        if ambiguous:
            self.stdout.write(self.style.WARNING(f"닉네임 중복 계정: {len(ambiguous)}건 (스킵)"))
            for nick, cnt in ambiguous:
                self.stdout.write(f"  ! {nick} ({cnt} accounts)")

        if not resolved:
            raise CommandError("발급 가능한 사용자가 없습니다.")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 발급하지 않습니다."))
            return

        if not options["no_input"]:
            confirm = input(
                f"\n{len(resolved)}명에게 쿠폰팩(최대 {per_user}장/인) 발급합니다. 계속? (yes/no): "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소")
                return

        issued_users = 0
        total_coupons = 0
        for nick, user in resolved:
            try:
                result = issue_child_dept_coupon_pack_for_user(user)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL {nick} (user_id={user.id}): {exc}"))
                continue
            issued_users += 1
            total_coupons += result["total_issued"]
            self.stdout.write(
                f"  OK {nick} (user_id={user.id}): {result['total_issued']}장"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n완료: {issued_users}명 / 쿠폰 {total_coupons}장"
            )
        )
