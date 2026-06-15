"""
우주라이크 제휴 쿠폰 신청폼(2026-06-12~14) — WORLD_CUP_EVENT_SPECIAL 풀 전량 발급.
"""
from __future__ import annotations

from datetime import datetime, timezone

from coupons.child_dept_event import load_nicknames_from_excel, merge_nickname_lists

WORLD_CUP_PARTNER_CAMPAIGN_CODE = "WORLD_CUP_PARTNER_BULK_202606"
WORLD_CUP_PARTNER_ISSUE_KEY_NAMESPACE = "WORLD_CUP_PARTNER"

# 신청폼 11명 + 추가
WORLD_CUP_PARTNER_DEFAULT_NICKNAMES: tuple[str, ...] = (
    "개굴개굴",
    "sysy0612",
    "정민귱",
    "디니",
    "하하루",
    "유이",
    "chan",
    "맛집만간다",
    "보리보리",
    "seeub",
    "박세은",
    "딸기잼",
)

__all__ = [
    "WORLD_CUP_PARTNER_CAMPAIGN_CODE",
    "WORLD_CUP_PARTNER_DEFAULT_NICKNAMES",
    "WORLD_CUP_PARTNER_ISSUE_KEY_NAMESPACE",
    "ensure_world_cup_partner_event_data",
    "load_nicknames_from_excel",
    "merge_nickname_lists",
]


def ensure_world_cup_partner_event_data(*, db_alias: str | None = None) -> str:
    """월드컵 제휴 신청폼 일괄 발급 캠페인 시드."""
    from django.db import router

    from coupons.festival_jungdunbam import resolve_cloudsql_alias
    from coupons.models import Campaign
    from coupons.service import WORLD_CUP_EVENT_COUPON_EXPIRES_AT

    alias = db_alias or resolve_cloudsql_alias()
    # 2026-06-08 00:00:00 ~ 2026-06-21 23:59:59 (KST)
    start_at = datetime(2026, 6, 7, 15, 0, 0, tzinfo=timezone.utc)
    end_at = WORLD_CUP_EVENT_COUPON_EXPIRES_AT

    Campaign.objects.using(alias).update_or_create(
        code=WORLD_CUP_PARTNER_CAMPAIGN_CODE,
        defaults={
            "name": "월드컵 제휴 쿠폰 신청폼 일괄 발급",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {
                "trigger": "BULK_NICKNAME",
                "mode": "FULL_POOL",
                "coupon_type": "WORLD_CUP_EVENT_SPECIAL",
            },
        },
    )
    return alias or router.db_for_write(Campaign)
