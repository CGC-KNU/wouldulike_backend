"""
완전 치환(쿠폰/스탬프):
- to_user(대상)의 쿠폰/스탬프(지갑/이벤트)를 전부 삭제하고
- from_user(소스)의 쿠폰/스탬프 데이터를 to_user로 이관(user_id만 변경)

주의:
- Coupon에는 (user, coupon_type, campaign, issue_key) Unique 제약이 있어,
  to_user에 남아있는 쿠폰이 있으면 from_user 쿠폰 이관 시 충돌 가능.
  본 커맨드는 실행 전에 dry-run으로 충돌을 점검한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import connections, transaction

from coupons.models import Coupon, StampEvent, StampWallet


User = get_user_model()


@dataclass(frozen=True)
class _Counts:
    coupons: int
    wallets: int
    events: int


def _pick_coupon_db_alias() -> str:
    # 운영: cloudsql 사용. 로컬 sqlite/단일 DB 환경에서는 default로 fallback.
    return "cloudsql" if "cloudsql" in connections.databases else "default"


class Command(BaseCommand):
    help = "user_id 기준으로 쿠폰/스탬프 데이터를 완전 치환합니다 (from → to)."

    def add_arguments(self, parser):
        parser.add_argument("--from-user-id", type=int, required=True, help="소스 user id (데이터를 가져올 사용자)")
        parser.add_argument("--to-user-id", type=int, required=True, help="대상 user id (덮어쓸 사용자)")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제로 변경하지 않고 충돌/삭제/이관 규모만 출력",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help='확인 없이 바로 실행합니다 (dry-run이 아닐 때만 의미).',
        )
        parser.add_argument(
            "--coupon-db",
            type=str,
            default=None,
            help='쿠폰/스탬프 DB alias (기본: cloudsql 있으면 cloudsql, 아니면 default)',
        )

    def handle(self, *args, **options):
        from_user_id: int = options["from_user_id"]
        to_user_id: int = options["to_user_id"]
        dry_run: bool = options["dry_run"]
        no_input: bool = options["no_input"]
        coupon_db: str = options["coupon_db"] or _pick_coupon_db_alias()

        if from_user_id == to_user_id:
            raise CommandError("--from-user-id와 --to-user-id는 서로 달라야 합니다.")

        from_user = User.objects.filter(id=from_user_id).first()
        to_user = User.objects.filter(id=to_user_id).first()
        if not from_user:
            raise CommandError(f"from_user(id={from_user_id})를 찾을 수 없습니다.")
        if not to_user:
            raise CommandError(f"to_user(id={to_user_id})를 찾을 수 없습니다.")

        self.stdout.write(self.style.WARNING("=== 완전 치환(쿠폰/스탬프) 사전 점검 ==="))
        self.stdout.write(f"from_user: id={from_user.id}, kakao_id={getattr(from_user, 'kakao_id', None)}, nickname={getattr(from_user, 'nickname', None)}")
        self.stdout.write(f"to_user  : id={to_user.id}, kakao_id={getattr(to_user, 'kakao_id', None)}, nickname={getattr(to_user, 'nickname', None)}")
        self.stdout.write(f"coupon_db alias: {coupon_db}")
        self.stdout.write("")

        from_counts = self._counts(from_user_id, coupon_db)
        to_counts = self._counts(to_user_id, coupon_db)

        self.stdout.write("현재 데이터 개수:")
        self.stdout.write(f"  - from_user 쿠폰: {from_counts.coupons} / 지갑: {from_counts.wallets} / 이벤트: {from_counts.events}")
        self.stdout.write(f"  - to_user   쿠폰: {to_counts.coupons} / 지갑: {to_counts.wallets} / 이벤트: {to_counts.events}")
        self.stdout.write("")

        conflicts = self._detect_conflicts(from_user_id, to_user_id, coupon_db)
        if conflicts.coupon_guard_conflicts or conflicts.wallet_restaurant_conflicts:
            self.stdout.write(self.style.ERROR("충돌 가능성이 발견되었습니다."))
            if conflicts.coupon_guard_conflicts:
                self.stdout.write(self.style.ERROR(f"  - Coupon unique 충돌 후보: {conflicts.coupon_guard_conflicts}건"))
            if conflicts.wallet_restaurant_conflicts:
                self.stdout.write(self.style.ERROR(f"  - StampWallet (user, restaurant_id) 충돌 후보: {conflicts.wallet_restaurant_conflicts}건"))
            self.stdout.write(self.style.ERROR("완전 치환은 to_user 데이터를 먼저 삭제하므로, 실제 실행 시에는 충돌이 '대부분' 해소됩니다."))
            self.stdout.write(self.style.ERROR("다만 삭제가 제대로 되지 않는 환경/권한/DB alias 설정이면 실패할 수 있습니다."))
            self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN: 실제 변경은 수행하지 않습니다."))
            return

        if not no_input:
            self.stdout.write(self.style.WARNING("⚠️  to_user의 쿠폰/스탬프 데이터를 전부 삭제하고 from_user 데이터를 이관합니다."))
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("작업이 취소되었습니다."))
                return

        self.stdout.write(self.style.WARNING("실제 치환 작업을 시작합니다..."))

        with transaction.atomic(using=coupon_db):
            deleted_coupons = Coupon.objects.using(coupon_db).filter(user_id=to_user_id).delete()[0]
            deleted_wallets = StampWallet.objects.using(coupon_db).filter(user_id=to_user_id).delete()[0]
            deleted_events = StampEvent.objects.using(coupon_db).filter(user_id=to_user_id).delete()[0]

            moved_coupons = Coupon.objects.using(coupon_db).filter(user_id=from_user_id).update(user_id=to_user_id)
            moved_wallets = StampWallet.objects.using(coupon_db).filter(user_id=from_user_id).update(user_id=to_user_id)
            moved_events = StampEvent.objects.using(coupon_db).filter(user_id=from_user_id).update(user_id=to_user_id)

        after_from = self._counts(from_user_id, coupon_db)
        after_to = self._counts(to_user_id, coupon_db)

        self.stdout.write(self.style.SUCCESS("=== 완료 ==="))
        self.stdout.write("삭제(to_user):")
        self.stdout.write(f"  - 쿠폰 {deleted_coupons} / 지갑 {deleted_wallets} / 이벤트 {deleted_events}")
        self.stdout.write("이관(from→to):")
        self.stdout.write(f"  - 쿠폰 {moved_coupons} / 지갑 {moved_wallets} / 이벤트 {moved_events}")
        self.stdout.write("")
        self.stdout.write("사후 검증:")
        self.stdout.write(f"  - from_user 잔여 쿠폰/지갑/이벤트: {after_from.coupons}/{after_from.wallets}/{after_from.events}")
        self.stdout.write(f"  - to_user   쿠폰/지갑/이벤트: {after_to.coupons}/{after_to.wallets}/{after_to.events}")

    def _counts(self, user_id: int, coupon_db: str) -> _Counts:
        return _Counts(
            coupons=Coupon.objects.using(coupon_db).filter(user_id=user_id).count(),
            wallets=StampWallet.objects.using(coupon_db).filter(user_id=user_id).count(),
            events=StampEvent.objects.using(coupon_db).filter(user_id=user_id).count(),
        )

    @dataclass(frozen=True)
    class _Conflicts:
        coupon_guard_conflicts: int
        wallet_restaurant_conflicts: int

    def _detect_conflicts(self, from_user_id: int, to_user_id: int, coupon_db: str) -> _Conflicts:
        # Coupon unique guard key: (coupon_type_id, campaign_id, issue_key)
        to_keys = set(
            Coupon.objects.using(coupon_db)
            .filter(user_id=to_user_id)
            .values_list("coupon_type_id", "campaign_id", "issue_key")
        )
        from_keys = set(
            Coupon.objects.using(coupon_db)
            .filter(user_id=from_user_id)
            .values_list("coupon_type_id", "campaign_id", "issue_key")
        )
        coupon_conflicts = len(to_keys & from_keys)

        to_restaurants = set(
            StampWallet.objects.using(coupon_db)
            .filter(user_id=to_user_id)
            .values_list("restaurant_id", flat=True)
        )
        from_restaurants = set(
            StampWallet.objects.using(coupon_db)
            .filter(user_id=from_user_id)
            .values_list("restaurant_id", flat=True)
        )
        wallet_conflicts = len(to_restaurants & from_restaurants)
        return self._Conflicts(
            coupon_guard_conflicts=coupon_conflicts,
            wallet_restaurant_conflicts=wallet_conflicts,
        )

