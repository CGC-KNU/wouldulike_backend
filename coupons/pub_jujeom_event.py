"""
주점·술집 이벤트 쿠폰(PUB_JUJEOM_EVENT) — CloudSQL 반영용 공통 로직.
"""
from __future__ import annotations

from datetime import datetime, timezone

from coupons.festival_jungdunbam import (
    RESTAURANT_ID as JUNGDUNBAM_FESTIVAL_RESTAURANT_ID,
    resolve_cloudsql_alias,
)

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


def _pub_jujeom_target_ids_from_connection(connection) -> set[int]:
    """restaurants_affiliate raw SQL (마이그레이션 state 모델에 is_affiliate 없을 때 대비)."""
    target: set[int] = set()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT restaurant_id, category, pub_option
            FROM restaurants_affiliate
            WHERE is_affiliate = TRUE
            """
        )
        for rid, cat, pub in cursor.fetchall():
            cat = (cat or "").strip()
            pub = (pub or "").strip()
            is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
            if cat == AFFILIATE_CATEGORY_JUJEOM or is_pub:
                target.add(int(rid))
    return target


def pub_jujeom_target_restaurant_ids(*, db_alias: str) -> set[int]:
    from django.db import connections

    from coupons.festival_jungdunbam import festival_restaurant_ids_excluded_from_pub_pools

    conn = connections[db_alias]
    if conn.vendor == "sqlite":
        from django.core.exceptions import FieldError
        from restaurants.models import AffiliateRestaurant

        target: set[int] = set()
        try:
            rows = (
                AffiliateRestaurant.objects.using(db_alias)
                .filter(is_affiliate=True)
                .values("restaurant_id", "pub_option", "category")
            )
        except FieldError:
            rows = []
        for row in rows:
            rid = int(row["restaurant_id"])
            cat = (row.get("category") or "").strip()
            pub = (row.get("pub_option") or "").strip()
            is_pub = pub == "네" or pub.startswith("네,") or cat == "술집"
            if cat == AFFILIATE_CATEGORY_JUJEOM or is_pub:
                target.add(rid)
    else:
        target = _pub_jujeom_target_ids_from_connection(conn)

    target -= festival_restaurant_ids_excluded_from_pub_pools()
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

    source_benefits = list(
        RestaurantCouponBenefit.objects.using(alias).filter(
            coupon_type=source_type,
            restaurant_id__in=target_ids,
            active=True,
        )
    )
    by_rid = {b.restaurant_id: b for b in source_benefits}
    template = source_benefits[0] if source_benefits else None

    for rid in target_ids:
        if rid == JUNGDUNBAM_FESTIVAL_RESTAURANT_ID:
            continue
        src = by_rid.get(rid)
        if src:
            defaults = {
                "title": src.title,
                "subtitle": PUB_JUJEOM_SUBTITLE,
                "benefit_json": src.benefit_json,
                "notes": getattr(src, "notes", "") or "",
                "active": True,
            }
        elif template:
            defaults = {
                "title": template.title,
                "subtitle": PUB_JUJEOM_SUBTITLE,
                "benefit_json": template.benefit_json,
                "notes": getattr(template, "notes", "") or "",
                "active": True,
            }
        else:
            defaults = {
                "title": "주점·술집 이벤트 쿠폰",
                "subtitle": PUB_JUJEOM_SUBTITLE,
                "benefit_json": {"type": "fixed", "value": 3000},
                "notes": "",
                "active": True,
            }
        RestaurantCouponBenefit.objects.using(alias).update_or_create(
            coupon_type=pub_type,
            restaurant_id=rid,
            sort_order=0,
            defaults=defaults,
        )

    RestaurantCouponBenefit.objects.using(alias).filter(
        coupon_type=pub_type,
        restaurant_id=JUNGDUNBAM_FESTIVAL_RESTAURANT_ID,
    ).update(active=False)

    return alias
