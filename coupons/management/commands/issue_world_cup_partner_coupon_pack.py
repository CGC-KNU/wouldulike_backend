"""
월드컵 제휴 쿠폰 신청폼 닉네임에게 WORLD_CUP_EVENT_SPECIAL 풀 전량 발급.

사용 예:
  python manage.py issue_world_cup_partner_coupon_pack --dry-run
  python manage.py issue_world_cup_partner_coupon_pack --no-input
  python manage.py issue_world_cup_partner_coupon_pack --only-provided --nickname 딸기잼 --no-input
  python manage.py issue_world_cup_partner_coupon_pack --excel /path/to/form.xlsx --no-input
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import router

from coupons.service import (
    WORLD_CUP_EVENT_COUPON_TYPE_CODE,
    WORLD_CUP_SUBTITLE,
    issue_world_cup_partner_pack_for_user,
)
from coupons.world_cup_partner_event import (
    WORLD_CUP_PARTNER_DEFAULT_NICKNAMES,
    load_nicknames_from_excel,
    merge_nickname_lists,
)
from coupons.models import RestaurantCouponBenefit
from restaurants.models import AffiliateRestaurant

User = get_user_model()


def _world_cup_partner_pool_benefits() -> list[RestaurantCouponBenefit]:
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)
    return list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type__code=WORLD_CUP_EVENT_COUPON_TYPE_CODE, active=True)
        .order_by("restaurant_id", "sort_order")
    )


def _world_cup_partner_pool_count() -> int:
    return len(_world_cup_partner_pool_benefits())


def _restaurant_name_map(restaurant_ids: list[int]) -> dict[int, str]:
    if not restaurant_ids:
        return {}
    alias = router.db_for_read(AffiliateRestaurant)
    rows = (
        AffiliateRestaurant.objects.using(alias)
        .filter(restaurant_id__in=restaurant_ids)
        .values_list("restaurant_id", "name")
    )
    return {rid: name for rid, name in rows}


def _format_coupon_line(coupon) -> str:
    snap = coupon.benefit_snapshot or {}
    restaurant_name = snap.get("restaurant_name") or f"식당#{coupon.restaurant_id}"
    title = snap.get("title") or ""
    return (
        f"    - {restaurant_name} | {title} | "
        f"code={coupon.code} | restaurant_id={coupon.restaurant_id}"
    )


class Command(BaseCommand):
    help = "월드컵 제휴 신청 닉네임에게 WORLD_CUP_EVENT_SPECIAL 풀 전량 발급"

    def add_arguments(self, parser):
        parser.add_argument("--excel", type=str, default=None)
        parser.add_argument("--nickname", action="append", default=[])
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-input", action="store_true")
        parser.add_argument("--only-provided", action="store_true")

    def handle(self, *args, **options):
        nick_lists: list[list[str]] = []
        if not options["only_provided"]:
            nick_lists.append(list(WORLD_CUP_PARTNER_DEFAULT_NICKNAMES))
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

        pool_benefits = _world_cup_partner_pool_benefits()
        pool_count = len(pool_benefits)
        name_map = _restaurant_name_map([b.restaurant_id for b in pool_benefits])

        self.stdout.write(
            f"\n쿠폰팩: {WORLD_CUP_SUBTITLE}\n"
            f"풀: {WORLD_CUP_EVENT_COUPON_TYPE_CODE} (월드컵 제휴 전체) / 사용자당 {pool_count}장\n"
        )
        self.stdout.write("발급 쿠폰 목록 (풀):")
        for benefit in pool_benefits:
            restaurant_name = name_map.get(benefit.restaurant_id, f"식당#{benefit.restaurant_id}")
            notes = f" ({benefit.notes})" if benefit.notes else ""
            self.stdout.write(
                f"  - {restaurant_name} | {benefit.title}{notes} | restaurant_id={benefit.restaurant_id}"
            )

        self.stdout.write(f"\n대상 닉네임 {len(nicknames)}명:\n")
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
                f"\n{len(resolved)}명에게 월드컵 제휴 쿠폰 "
                f"{pool_count}장씩 발급합니다. 계속? (yes/no): "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소")
                return

        issued_users = 0
        total_coupons = 0
        for nick, user in resolved:
            try:
                result = issue_world_cup_partner_pack_for_user(user)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  FAIL {nick} (user_id={user.id}): {exc}"))
                continue
            issued_users += 1
            coupons = result.get("coupons") or []
            total_coupons += result["total_issued"]
            flag = " (기발급)" if result.get("already_issued") else ""
            self.stdout.write(
                f"\n  OK {nick} (user_id={user.id}): {result['total_issued']}장{flag}"
            )
            for coupon in coupons:
                self.stdout.write(_format_coupon_line(coupon))

        self.stdout.write(
            self.style.SUCCESS(f"\n완료: {issued_users}명 / 쿠폰 {total_coupons}장")
        )
