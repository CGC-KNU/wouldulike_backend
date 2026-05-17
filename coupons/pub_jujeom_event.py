"""
주점·술집 이벤트 쿠폰(PUB_JUJEOM_EVENT) — CloudSQL 반영용 공통 로직.
"""
from __future__ import annotations

from datetime import datetime, timezone

from coupons.festival_jungdunbam import resolve_cloudsql_alias

PUB_JUJEOM_EVENT_COUPON_TYPE_CODE = "PUB_JUJEOM_EVENT"
PUB_JUJEOM_EVENT_CAMPAIGN_CODE = "PUB_JUJEOM_EVENT_CODES"
PUB_JUJEOM_SUBTITLE = "[주점 이벤트 🍻]"
AFFILIATE_CATEGORY_JUJEOM = "주점"

FESTIVAL_START_KST = datetime(2026, 5, 1, 0, 0, 0)
FESTIVAL_END_KST = datetime(2026, 5, 31, 23, 59, 59)


def _kst_aware(dt: datetime):
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    return dt.replace(tzinfo=ZoneInfo("Asia/Seoul"))


def pub_jujeom_target_restaurant_ids(*, db_alias: str) -> set[int]:
    from restaurants.models import AffiliateRestaurant

    target: set[int] = set()
    for row in (
        AffiliateRestaurant.objects.using(db_alias)
        .filter(is_affiliate=True)
        .values("restaurant_id", "pub_option", "category")
    ):
        rid = int(row["restaurant_id"])
        cat = (row.get("category") or "").strip()
        pub = (row.get("pub_option") or "").strip()
        is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
        if cat == AFFILIATE_CATEGORY_JUJEOM or is_pub:
            target.add(rid)
    return target


def ensure_pub_jujeom_event_data(*, db_alias: str | None = None) -> str:
    """CouponType / Campaign / RestaurantCouponBenefit 을 idempotent 하게 반영. 반환: DB alias."""
    from coupons.models import Campaign, CouponType, RestaurantCouponBenefit

    alias = db_alias or resolve_cloudsql_alias()
    start_at = _kst_aware(FESTIVAL_START_KST)
    end_at = _kst_aware(FESTIVAL_END_KST)

    CouponType.objects.using(alias).update_or_create(
        code=PUB_JUJEOM_EVENT_COUPON_TYPE_CODE,
        defaults={
            "title": PUB_JUJEOM_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )
    Campaign.objects.using(alias).update_or_create(
        code=PUB_JUJEOM_EVENT_CAMPAIGN_CODE,
        defaults={
            "name": "주점 이벤트 쿠폰 (JUNYOUNG/JEONGHWAN/YUNJI)",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {
                "trigger": "COUPON_CODE",
                "codes": {"JUNYOUNG": 1, "JEONGHWAN": 3, "YUNJI": 5},
            },
        },
    )

    pub_type = CouponType.objects.using(alias).get(code=PUB_JUJEOM_EVENT_COUPON_TYPE_CODE)
    target_ids = pub_jujeom_target_restaurant_ids(db_alias=alias)
    if not target_ids:
        return alias

    source_type = None
    for code in ("GAEHWALIKE", "MIDTERM_EVENT_SPECIAL"):
        try:
            source_type = CouponType.objects.using(alias).get(code=code)
            break
        except CouponType.DoesNotExist:
            continue
    if source_type is None:
        return alias

    source_benefits = RestaurantCouponBenefit.objects.using(alias).filter(
        coupon_type=source_type,
        restaurant_id__in=target_ids,
        active=True,
    )
    for benefit in source_benefits:
        RestaurantCouponBenefit.objects.using(alias).update_or_create(
            coupon_type=pub_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": PUB_JUJEOM_SUBTITLE,
                "benefit_json": benefit.benefit_json,
                "notes": getattr(benefit, "notes", "") or "",
                "active": benefit.active,
            },
        )

    return alias
