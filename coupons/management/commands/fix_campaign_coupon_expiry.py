import math

from django.core.management.base import BaseCommand
from django.db import router
from django.utils import timezone

from coupons.models import Campaign, Coupon


class Command(BaseCommand):
    help = (
        "캠페인(end_at)이 있는 쿠폰 중 만료일(expires_at)이 캠페인 기한을 넘는 경우를 찾아 "
        "캠페인 종료시각으로 수정합니다. (기획전 쿠폰 만료일 일괄 정정)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--campaign-code",
            type=str,
            default=None,
            help="특정 캠페인 코드만 대상으로 제한 (미지정 시 전체)",
        )
        parser.add_argument(
            "--statuses",
            type=str,
            default="ISSUED",
            help='대상 쿠폰 status 콤마구분 (기본: "ISSUED")',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 업데이트 없이 대상 건수/샘플만 출력",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2000,
            help="업데이트 배치 크기 (기본 2000)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="처리 최대 건수 제한 (디버깅용)",
        )

    def handle(self, *args, **options):
        campaign_code = (options.get("campaign_code") or "").strip() or None
        dry_run = bool(options.get("dry_run"))
        batch_size = int(options.get("batch_size") or 2000)
        limit = options.get("limit")
        statuses = [
            s.strip().upper()
            for s in (options.get("statuses") or "").split(",")
            if s.strip()
        ] or ["ISSUED"]

        alias = router.db_for_write(Coupon)

        camp_qs = Campaign.objects.using(alias).filter(active=True, end_at__isnull=False)
        if campaign_code:
            camp_qs = camp_qs.filter(code=campaign_code)
        camps = list(camp_qs.only("id", "code", "end_at"))
        if not camps:
            self.stdout.write(self.style.WARNING("대상 캠페인이 없습니다. (end_at 또는 code 확인)"))
            return

        camp_map = {c.id: c for c in camps}
        camp_ids = list(camp_map.keys())

        qs = (
            Coupon.objects.using(alias)
            .filter(campaign_id__in=camp_ids, status__in=statuses)
            .exclude(expires_at__isnull=True)
            .only("id", "code", "campaign_id", "expires_at")
            .order_by("id")
        )

        if limit is not None:
            qs = qs[: int(limit)]

        # 캠페인 end_at보다 늦게 만료되는 쿠폰만 대상
        target_ids: list[int] = []
        scanned = 0
        for c in qs.iterator(chunk_size=2000):
            scanned += 1
            camp = camp_map.get(c.campaign_id)
            if not camp or not camp.end_at:
                continue
            if timezone.is_naive(c.expires_at):
                expires_at = timezone.make_aware(c.expires_at, timezone=timezone.utc)
            else:
                expires_at = c.expires_at
            end_at = camp.end_at
            if timezone.is_naive(end_at):
                end_at = timezone.make_aware(end_at, timezone=timezone.utc)

            if expires_at > end_at:
                target_ids.append(c.id)

        if not target_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    f"대상 없음. scanned={scanned}, statuses={statuses}, campaign_code={campaign_code or '*'}"
                )
            )
            return

        self.stdout.write(
            f"대상 쿠폰 수: {len(target_ids)} (scanned={scanned}, statuses={statuses}, dry_run={dry_run})"
        )

        # 샘플 5개 출력
        sample = list(
            Coupon.objects.using(alias)
            .filter(id__in=target_ids[:5])
            .select_related("campaign")
            .only("id", "code", "expires_at", "campaign__code", "campaign__end_at")
            .order_by("id")
        )
        for s in sample:
            self.stdout.write(
                f"- id={s.id} code={s.code} campaign={s.campaign.code if s.campaign else None} "
                f"expires_at={s.expires_at} campaign_end_at={getattr(s.campaign, 'end_at', None)}"
            )

        if dry_run:
            return

        # 실제 업데이트: 캠페인별로 end_at을 조회해 해당 캠페인 쿠폰을 end_at으로 덮어쓰기
        # (expires_at > end_at 조건은 Python에서 이미 걸렀으므로 안전)
        updated_total = 0
        # 캠페인별로 묶어서 update하면 SQL이 간단해짐
        by_campaign: dict[int, list[int]] = {}
        # target_ids를 다시 조회하여 (coupon_id, campaign_id) 얻기
        id_rows = (
            Coupon.objects.using(alias)
            .filter(id__in=target_ids)
            .values_list("id", "campaign_id")
        )
        for cid, camp_id in id_rows:
            by_campaign.setdefault(camp_id, []).append(cid)

        for camp_id, ids in by_campaign.items():
            camp = camp_map.get(camp_id)
            if not camp or not camp.end_at:
                continue
            end_at = camp.end_at
            if timezone.is_naive(end_at):
                end_at = timezone.make_aware(end_at, timezone=timezone.utc)

            batches = int(math.ceil(len(ids) / batch_size))
            for i in range(batches):
                chunk = ids[i * batch_size : (i + 1) * batch_size]
                updated = (
                    Coupon.objects.using(alias)
                    .filter(id__in=chunk)
                    .update(expires_at=end_at)
                )
                updated_total += updated

        self.stdout.write(self.style.SUCCESS(f"업데이트 완료: {updated_total}건"))

