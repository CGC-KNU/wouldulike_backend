"""
잘못 발급된 CHILD_DEPT_COUPON_PACK(주점·술집 9장) 쿠폰을 삭제합니다.

사용 예:
  python manage.py revert_child_dept_coupon_pack --dry-run
  python manage.py revert_child_dept_coupon_pack --no-input
  python manage.py revert_child_dept_coupon_pack --only-provided --nickname 딸기잼 --no-input
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from coupons.child_dept_event import (
    CHILD_DEPT_COUPON_TYPE_CODE,
    CHILD_DEPT_DEFAULT_NICKNAMES,
    CHILD_DEPT_ISSUE_KEY_NAMESPACE,
    load_nicknames_from_excel,
    merge_nickname_lists,
)
from coupons.models import Coupon
from coupons.service import revoke_child_dept_coupon_pack_for_user

User = get_user_model()


class Command(BaseCommand):
    help = "구 아동학부(주점 풀) CHILD_DEPT_COUPON_PACK 발급분 삭제"

    def add_arguments(self, parser):
        parser.add_argument("--excel", type=str, default=None)
        parser.add_argument("--nickname", action="append", default=[])
        parser.add_argument("--only-provided", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-input", action="store_true")
        parser.add_argument(
            "--include-redeemed",
            action="store_true",
            help="사용 완료(REDEEMED) 쿠폰도 삭제 (기본: ISSUED 만)",
        )
        parser.add_argument(
            "--all-users",
            action="store_true",
            help="닉네임 목록 무시, CHILD_DEPT_PACK 발급 전체 삭제",
        )

    def handle(self, *args, **options):
        coupon_alias = router.db_for_write(Coupon)
        qs = Coupon.objects.using(coupon_alias).filter(
            coupon_type__code=CHILD_DEPT_COUPON_TYPE_CODE,
            issue_key__startswith=f"{CHILD_DEPT_ISSUE_KEY_NAMESPACE}:",
        )
        if not options["include_redeemed"]:
            qs = qs.filter(status="ISSUED")

        if not options["all_users"]:
            nick_lists: list[list[str]] = []
            if not options["only_provided"]:
                nick_lists.append(list(CHILD_DEPT_DEFAULT_NICKNAMES))
            if options.get("nickname"):
                nick_lists.append(options["nickname"])
            if options.get("excel"):
                nick_lists.append(load_nicknames_from_excel(options["excel"]))
            nicknames = merge_nickname_lists(*nick_lists)
            if not nicknames:
                raise CommandError("대상 닉네임이 없습니다.")

            user_alias = router.db_for_read(User)
            user_ids: list[int] = []
            for nick in nicknames:
                uid = (
                    User.objects.using(user_alias)
                    .filter(nickname__iexact=nick)
                    .values_list("id", flat=True)
                    .first()
                )
                if uid:
                    user_ids.append(uid)
            qs = qs.filter(user_id__in=user_ids)

        count = qs.count()
        self.stdout.write(f"삭제 대상 CHILD_DEPT 쿠폰: {count}장")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("[DRY-RUN] 삭제하지 않습니다."))
            return

        if not options["no_input"]:
            confirm = input(f"{count}장 삭제합니다. 계속? (yes/no): ")
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소")
                return

        if options["all_users"]:
            deleted, _ = qs.delete()
        else:
            deleted = 0
            user_alias = router.db_for_read(User)
            for uid in qs.values_list("user_id", flat=True).distinct():
                user = User.objects.using(user_alias).get(id=uid)
                deleted += revoke_child_dept_coupon_pack_for_user(
                    user, include_redeemed=options["include_redeemed"]
                )

        self.stdout.write(self.style.SUCCESS(f"삭제 완료: {deleted}장"))
