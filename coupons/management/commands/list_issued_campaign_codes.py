from django.core.management.base import BaseCommand
from django.db import router
from django.db.models import Count, Max, Q
from django.utils import timezone

from coupons.models import Campaign, Coupon


class Command(BaseCommand):
    help = "쿠폰이 발급된(존재하는) 캠페인 코드 목록을 집계해 출력합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--statuses",
            type=str,
            default="ISSUED",
            help='대상 쿠폰 status 콤마구분 (기본: "ISSUED", 전체는 "ISSUED,REDEEMED,EXPIRED,CANCELED")',
        )
        parser.add_argument(
            "--include-null-campaign",
            action="store_true",
            help="campaign이 NULL인 쿠폰도 포함(별도 항목으로 표시)",
        )
        parser.add_argument(
            "--with-end-at-only",
            action="store_true",
            help="Campaign.end_at이 있는 캠페인만 출력",
        )
        parser.add_argument(
            "--only-active-campaigns",
            action="store_true",
            help="active=True 캠페인만 출력",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="최대 출력 개수 (기본 200)",
        )

    def handle(self, *args, **options):
        statuses = [
            s.strip().upper()
            for s in (options.get("statuses") or "").split(",")
            if s.strip()
        ] or ["ISSUED"]
        include_null_campaign = bool(options.get("include_null_campaign"))
        with_end_at_only = bool(options.get("with_end_at_only"))
        only_active_campaigns = bool(options.get("only_active_campaigns"))
        limit = int(options.get("limit") or 200)

        alias = router.db_for_read(Coupon)

        qs = Coupon.objects.using(alias).filter(status__in=statuses)
        if not include_null_campaign:
            qs = qs.filter(campaign_id__isnull=False)

        rows = (
            qs.values("campaign_id", "campaign__code", "campaign__active", "campaign__end_at")
            .annotate(
                coupon_count=Count("id"),
                max_expires_at=Max("expires_at"),
            )
            .order_by("-coupon_count", "campaign__code")
        )

        if with_end_at_only:
            rows = rows.filter(campaign__end_at__isnull=False)
        if only_active_campaigns:
            rows = rows.filter(campaign__active=True)

        rows = list(rows[:limit])
        if not rows:
            self.stdout.write(self.style.WARNING("조건에 해당하는 캠페인 코드가 없습니다."))
            return

        self.stdout.write(
            f"총 {len(rows)}개 (statuses={statuses}, include_null_campaign={include_null_campaign}, "
            f"with_end_at_only={with_end_at_only}, only_active_campaigns={only_active_campaigns})"
        )

        # end_at이 있는데 max_expires_at이 end_at을 넘는지 간단 표시
        for r in rows:
            camp_id = r.get("campaign_id")
            code = r.get("campaign__code") if camp_id else None
            active = r.get("campaign__active") if camp_id else None
            end_at = r.get("campaign__end_at") if camp_id else None
            cnt = r.get("coupon_count") or 0
            max_expires_at = r.get("max_expires_at")

            label = code or "(NULL_CAMPAIGN)"
            end_at_str = str(end_at) if end_at else "-"
            max_exp_str = str(max_expires_at) if max_expires_at else "-"

            exceeds = ""
            if end_at and max_expires_at:
                ea = end_at
                me = max_expires_at
                if timezone.is_naive(ea):
                    ea = timezone.make_aware(ea, timezone=timezone.utc)
                if timezone.is_naive(me):
                    me = timezone.make_aware(me, timezone=timezone.utc)
                if me > ea:
                    exceeds = "  [end_at<expires_at]"

            self.stdout.write(
                f"- {label}  count={cnt}  active={active}  end_at={end_at_str}  max_expires_at={max_exp_str}{exceeds}"
            )

