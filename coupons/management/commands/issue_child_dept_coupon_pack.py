"""
아동학부 쿠폰팩 일괄 발급 — 성년의날(GAEHWALIKE) 풀 10종, subtitle [아동학부 쿠폰팩 🐣].

사용 예:
  python manage.py revert_child_dept_coupon_pack --no-input   # 구(주점) 발급 복구
  python manage.py issue_child_dept_coupon_pack --dry-run
  python manage.py issue_child_dept_coupon_pack --no-input
  python manage.py issue_child_dept_coupon_pack --only-provided --nickname 딸기잼 --no-input
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from coupons.child_dept_event import (
    CHILD_DEPT_DEFAULT_NICKNAMES,
    CHILD_DEPT_SUBTITLE,
    load_nicknames_from_excel,
    merge_nickname_lists,
)
from coupons.service import GAEHWALIKE_COUPON_COUNT, issue_child_dept_coupon_pack_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "아동학부 신청 닉네임에게 GAEHWALIKE 풀 쿠폰팩(10종) 발급"

    def add_arguments(self, parser):
        parser.add_argument("--excel", type=str, default=None)
        parser.add_argument("--nickname", action="append", default=[])
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-input", action="store_true")
        parser.add_argument("--only-provided", action="store_true")

    def handle(self, *args, **options):
        nick_lists: list[list[str]] = []
        if not options["only_provided"]:
            nick_lists.append(list(CHILD_DEPT_DEFAULT_NICKNAMES))
        if options.get("nickname"):
            nick_lists.append(options["nickname"])
        if options.get("excel"):
            try:
                nick_lists.append(load_nicknames_from_excel(options["excel"]))
            except FileNotFoundError:
                raise CommandError(f"엑셀 파일 없음: {options['excel']}")
            except Exception as exc:
                raise CommandError(f"엑셀 읽기 실패: {exc}") from exc

        nicknames = merge_nickname_lists(*nick_lists)
        if not nicknames:
            raise CommandError("발급 대상 닉네임이 없습니다.")

        self.stdout.write(
            f"\n쿠폰팩: {CHILD_DEPT_SUBTITLE}\n"
            f"풀: GAEHWALIKE (성년의날 제휴 전체) / 사용자당 {GAEHWALIKE_COUPON_COUNT}장\n"
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
                f"\n{len(resolved)}명에게 GAEHWALIKE 풀 쿠폰 "
                f"{GAEHWALIKE_COUPON_COUNT}장씩 발급합니다. 계속? (yes/no): "
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
            flag = " (기발급)" if result.get("already_issued") else ""
            self.stdout.write(
                f"  OK {nick} (user_id={user.id}): {result['total_issued']}장{flag}"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\n완료: {issued_users}명 / 쿠폰 {total_coupons}장")
        )
