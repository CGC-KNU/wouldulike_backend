"""
쿠폰이 없는 사용자에게 신규가입 쿠폰을 일괄 발급합니다.

사용 예:
  python manage.py issue_signup_coupons_bulk --dry-run
  python manage.py issue_signup_coupons_bulk --since 2026-02-28 --until 2026-03-03
  python manage.py issue_signup_coupons_bulk --recent-days 7
  python manage.py issue_signup_coupons_bulk --no-input
"""
from django.core.management.base import BaseCommand
from django.db import router
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime

from coupons.models import Coupon
from coupons.service import ensure_invite_code, issue_signup_coupon

User = get_user_model()


class Command(BaseCommand):
    help = "쿠폰이 없는 사용자에게 신규가입 쿠폰 일괄 발급"

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
        parser.add_argument(
            "--since",
            type=str,
            metavar="YYYY-MM-DD",
            help="가입일 시작 (이후 가입자만, 예: 2026-02-28)",
        )
        parser.add_argument(
            "--until",
            type=str,
            metavar="YYYY-MM-DD",
            help="가입일 종료 (이전 가입자만, 예: 2026-03-03)",
        )
        parser.add_argument(
            "--recent-days",
            type=int,
            metavar="N",
            help="최근 N일 이내 가입자만 (예: 7)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            metavar="N",
            help="최대 N명만 처리 (테스트용)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        no_input = options["no_input"]
        since = options.get("since")
        until = options.get("until")
        recent_days = options.get("recent_days")
        limit = options.get("limit")

        alias = router.db_for_read(Coupon)

        # 1) 쿠폰이 있는 user_id
        users_with_coupons = set(
            Coupon.objects.using(alias)
            .values_list("user_id", flat=True)
            .distinct()
        )

        # 2) 전체 사용자 중 쿠폰 없는 사람
        qs = User.objects.exclude(id__in=users_with_coupons).order_by("id")

        # 3) 날짜 필터
        if since:
            try:
                dt = datetime.strptime(since, "%Y-%m-%d")
                start = timezone.make_aware(datetime(dt.year, dt.month, dt.day, 0, 0, 0))
                qs = qs.filter(created_at__gte=start)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"잘못된 날짜 형식: {since} (YYYY-MM-DD)"))
                return

        if until:
            try:
                dt = datetime.strptime(until, "%Y-%m-%d")
                end = timezone.make_aware(datetime(dt.year, dt.month, dt.day, 23, 59, 59))
                qs = qs.filter(created_at__lte=end)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"잘못된 날짜 형식: {until} (YYYY-MM-DD)"))
                return

        if recent_days:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=recent_days)
            qs = qs.filter(created_at__gte=cutoff)

        if limit:
            qs = qs[:limit]

        users = list(qs.values_list("id", "kakao_id", "created_at"))

        if not users:
            self.stdout.write(self.style.SUCCESS("발급 대상이 없습니다."))
            return

        self.stdout.write(f"\n쿠폰 없는 사용자: {len(users)}명")
        if since or until or recent_days:
            self.stdout.write(f"  필터: since={since or '-'}, until={until or '-'}, recent_days={recent_days or '-'}")
        self.stdout.write("-" * 70)
        for uid, kid, created in users[:20]:
            kid_str = str(kid) if kid else "-"
            self.stdout.write(f"  user_id={uid}, kakao_id={kid_str}, 가입일={created}")
        if len(users) > 20:
            self.stdout.write(f"  ... 외 {len(users) - 20}명")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제 변경 없이 종료합니다."))
            return

        if not no_input:
            confirm = input(f"\n위 {len(users)}명에게 신규가입 쿠폰을 발급합니다. 계속하시겠습니까? (yes/no): ")
            if confirm.strip().lower() != "yes":
                self.stdout.write("취소되었습니다.")
                return

        success = 0
        fail = 0

        for uid, kid, created in users:
            try:
                user = User.objects.get(id=uid)
                ensure_invite_code(user)
                issued = issue_signup_coupon(user)
                if issued:
                    rid = issued[0].restaurant_id
                    self.stdout.write(
                        self.style.SUCCESS(f"  user_id={uid}: 발급 완료 (restaurant_id={rid})")
                    )
                    success += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  user_id={uid}: 발급 실패 (대상 식당 없음)")
                    )
                    fail += 1
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  user_id={uid}: 사용자 없음"))
                fail += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  user_id={uid}: 오류 - {e}"))
                fail += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"완료: 성공 {success}명, 실패 {fail}명"))
