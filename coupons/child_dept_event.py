"""
아동학부 쿠폰팩 — 주점·술집 풀에서 1·3·5종 랜덤 발급 (PUB_JUJEOM 과 동일 풀, subtitle 만 다름).
"""
from __future__ import annotations

from datetime import datetime

from coupons.festival_jungdunbam import resolve_cloudsql_alias
from coupons.pub_jujeom_event import (
    FESTIVAL_END_KST,
    FESTIVAL_START_KST,
    _kst_aware,
    pub_jujeom_target_restaurant_ids,
)

CHILD_DEPT_COUPON_TYPE_CODE = "CHILD_DEPT_COUPON_PACK"
CHILD_DEPT_CAMPAIGN_CODE = "CHILD_DEPT_COUPON_PACK_202605"
CHILD_DEPT_SUBTITLE = "[아동학부 쿠폰팩 🐣]"

# PUB_JUJEOM 과 동일 1·3·5종 구성
CHILD_DEPT_PACK_TIER_COUNTS: dict[str, int] = {
    "JUNYOUNG": 1,
    "JEONGHWAN": 3,
    "YUNJI": 5,
}

# 5월 아동학부 신청폼(17명) + 추가
CHILD_DEPT_DEFAULT_NICKNAMES: tuple[str, ...] = (
    "맛집만간다",
    "노란포스트잇",
    "디니",
    "sysy0612",
    "이지은",
    "chan",
    "김주연",
    "라라미",
    "dawon1028",
    "haiiiigo",
    "hk",
    "tying2014",
    "쪼롱",
    "박세은",
    "하하루",
    "아료니",
    "죵재",
    "딸기잼잼",
    "딸기잼",
)


def ensure_child_dept_event_data(*, db_alias: str | None = None) -> str:
    from coupons.models import Campaign, CouponType, RestaurantCouponBenefit

    alias = db_alias or resolve_cloudsql_alias()
    start_at = _kst_aware(FESTIVAL_START_KST)
    end_at = _kst_aware(FESTIVAL_END_KST)

    CouponType.objects.using(alias).update_or_create(
        code=CHILD_DEPT_COUPON_TYPE_CODE,
        defaults={
            "title": CHILD_DEPT_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )
    Campaign.objects.using(alias).update_or_create(
        code=CHILD_DEPT_CAMPAIGN_CODE,
        defaults={
            "name": "아동학부 쿠폰팩 2026-05",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {"tiers": CHILD_DEPT_PACK_TIER_COUNTS},
        },
    )

    child_type = CouponType.objects.using(alias).get(code=CHILD_DEPT_COUPON_TYPE_CODE)
    target_ids = pub_jujeom_target_restaurant_ids(db_alias=alias)
    if not target_ids:
        return alias

    source_type = None
    for code in ("PUB_JUJEOM_EVENT", "GAEHWALIKE", "MIDTERM_EVENT_SPECIAL"):
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
            coupon_type=child_type,
            restaurant_id=benefit.restaurant_id,
            sort_order=getattr(benefit, "sort_order", 0),
            defaults={
                "title": benefit.title,
                "subtitle": CHILD_DEPT_SUBTITLE,
                "benefit_json": benefit.benefit_json,
                "notes": getattr(benefit, "notes", "") or "",
                "active": benefit.active,
            },
        )

    return alias


def load_nicknames_from_excel(path: str) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    nicknames: list[str] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        if not row or len(row) < 6:
            continue
        fee = (row[4] or "").strip() if row[4] is not None else ""
        if fee and fee.upper() not in ("O", "Y", "YES", "예"):
            continue
        nick = (row[5] or "").strip() if row[5] is not None else ""
        if nick:
            nicknames.append(nick)
    wb.close()
    return nicknames


def merge_nickname_lists(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in lists:
        for nick in raw:
            key = nick.strip()
            if not key:
                continue
            fold = key.casefold()
            if fold in seen:
                continue
            seen.add(fold)
            out.append(key)
    return out
