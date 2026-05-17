from __future__ import annotations

from datetime import datetime, time, timezone as dt_timezone

from django.db import migrations
from django.db.models import Max, Min


MEDIUM_RARE_CAMPAIGN_CODE = "MEDIUM_RARE_EVENT"


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Coupon = apps.get_model("coupons", "Coupon")

    camp = Campaign.objects.filter(code=MEDIUM_RARE_CAMPAIGN_CODE).first()
    if not camp:
        return

    agg = (
        Coupon.objects.filter(campaign=camp)
        .aggregate(min_issued_at=Min("issued_at"), max_issued_at=Max("issued_at"))
    )
    min_issued_at = agg.get("min_issued_at")
    max_issued_at = agg.get("max_issued_at")
    if not min_issued_at or not max_issued_at:
        return

    # 캠페인 기간을 "발급이 실제로 일어난 날짜 범위"로 설정.
    # - start_at: 최초 발급 시각
    # - end_at: 마지막 발급이 일어난 날짜의 23:59:59 (KST 기준) → UTC로 저장
    #
    # 주의: issued_at은 tz-aware로 저장되는 것이 정상. tz 정보가 없을 경우 UTC로 간주.
    if getattr(min_issued_at, "tzinfo", None) is None:
        min_issued_at = min_issued_at.replace(tzinfo=dt_timezone.utc)
    if getattr(max_issued_at, "tzinfo", None) is None:
        max_issued_at = max_issued_at.replace(tzinfo=dt_timezone.utc)

    try:
        from zoneinfo import ZoneInfo

        kst = ZoneInfo("Asia/Seoul")
        last_day_kst = max_issued_at.astimezone(kst).date()
        end_at_kst = datetime.combine(last_day_kst, time(23, 59, 59), tzinfo=kst)
        end_at_utc = end_at_kst.astimezone(dt_timezone.utc)
    except Exception:
        # zoneinfo 미지원 환경 폴백: UTC 날짜 기준으로 23:59:59
        last_day_utc = max_issued_at.astimezone(dt_timezone.utc).date()
        end_at_utc = datetime.combine(last_day_utc, time(23, 59, 59), tzinfo=dt_timezone.utc)

    # 캠페인 기간 저장(기존 값이 있더라도 운영 정책상 기간형으로 강제)
    Campaign.objects.filter(id=camp.id).update(start_at=min_issued_at, end_at=end_at_utc)

    # 이미 발급된 쿠폰의 만료일이 end_at을 넘으면 end_at으로 당김
    Coupon.objects.filter(campaign=camp, expires_at__gt=end_at_utc).update(expires_at=end_at_utc)


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    # 되돌릴 때는 기간 정보만 제거 (쿠폰 만료일 복원은 불가/비의도)
    Campaign.objects.filter(code=MEDIUM_RARE_CAMPAIGN_CODE).update(start_at=None, end_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0050_fix_midterm_jubi_americano_typo"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

