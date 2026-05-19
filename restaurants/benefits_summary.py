"""
제휴 식당(coupons + StampRewardRule)의 쿠폰 혜택을 restaurants_affiliate.coupon_benefits_summary 에 넣기 위한 집계.

- 신규가입: WELCOME_3000
- 친구초대: REFERRAL_BONUS_REFERRER / REFERRAL_BONUS_REFEREE
- 스탬프: StampRewardRule + RestaurantCouponBenefit (get_stamp_rewards_for_restaurant 와 동일 소스)
"""
from __future__ import annotations

from django.db import router
from django.utils import timezone

from coupons.models import RestaurantCouponBenefit
from coupons.service import (
    _get_excluded_restaurant_ids,
    _get_legacy_config,
    _get_stamp_reward_rule,
    _is_stamp_disabled_restaurant,
    get_stamp_rewards_for_restaurant,
)

SIGNUP_COUPON_CODE = "WELCOME_3000"
REFERRAL_REFERRER_CODE = "REFERRAL_BONUS_REFERRER"
REFERRAL_REFEREE_CODE = "REFERRAL_BONUS_REFEREE"


def _benefit_db_alias() -> str:
    return router.db_for_read(RestaurantCouponBenefit)


def _serialize_benefit_rows(
    benefits: list[RestaurantCouponBenefit],
) -> list[dict]:
    return [
        {
            "title": b.title,
            "subtitle": b.subtitle,
            "notes": b.notes or "",
            "benefit": b.benefit_json or {},
            "sort_order": b.sort_order,
        }
        for b in benefits
    ]


def _fetch_active_benefits(
    restaurant_id: int,
    coupon_type_code: str,
    *,
    db_alias: str | None = None,
) -> list[RestaurantCouponBenefit]:
    alias = db_alias or _benefit_db_alias()
    return list(
        RestaurantCouponBenefit.objects.using(alias)
        .filter(
            restaurant_id=restaurant_id,
            coupon_type__code=coupon_type_code,
            active=True,
        )
        .select_related("coupon_type")
        .order_by("sort_order", "id")
    )


def _coupon_type_section(
    restaurant_id: int,
    coupon_type_code: str,
    *,
    db_alias: str | None = None,
) -> dict:
    excluded = restaurant_id in _get_excluded_restaurant_ids(
        coupon_type_code, db_alias=db_alias
    )
    items = _serialize_benefit_rows(
        _fetch_active_benefits(restaurant_id, coupon_type_code, db_alias=db_alias)
    )
    return {
        "coupon_type_code": coupon_type_code,
        "eligible": not excluded and bool(items),
        "excluded": excluded,
        "items": items,
    }


def _stamp_section(restaurant_id: int) -> dict:
    if _is_stamp_disabled_restaurant(restaurant_id):
        rule = _get_stamp_reward_rule(restaurant_id)
        cfg = rule.config_json if rule else {}
        if not isinstance(cfg, dict):
            cfg = {}
        display_rewards = cfg.get("display_rewards") or []
        return {
            "enabled": False,
            "rule_type": rule.rule_type if rule else None,
            "notes": cfg.get("notes") or "",
            "cycle_target": cfg.get("cycle_target"),
            "rewards": display_rewards,
        }

    rule = _get_stamp_reward_rule(restaurant_id)
    if rule:
        cfg = rule.config_json or {}
        rule_type = rule.rule_type
        notes = cfg.get("notes") or ""
        cycle_target = cfg.get("cycle_target")
    else:
        cfg = _get_legacy_config()
        rule_type = "THRESHOLD"
        notes = cfg.get("notes") or ""
        cycle_target = cfg.get("cycle_target", 10)

    return {
        "enabled": True,
        "rule_type": rule_type,
        "notes": notes,
        "cycle_target": cycle_target,
        "rewards": get_stamp_rewards_for_restaurant(restaurant_id),
    }


def build_coupon_benefits_summary(
    restaurant_id: int,
    *,
    db_alias: str | None = None,
) -> dict:
    """식당 1곳의 신규가입·친구초대·스탬프 혜택을 JSON으로 집계."""
    alias = db_alias or _benefit_db_alias()
    return {
        "restaurant_id": restaurant_id,
        "generated_at": timezone.now().isoformat(),
        "signup": _coupon_type_section(
            restaurant_id, SIGNUP_COUPON_CODE, db_alias=alias
        ),
        "referral": {
            "referrer": _coupon_type_section(
                restaurant_id, REFERRAL_REFERRER_CODE, db_alias=alias
            ),
            "referee": _coupon_type_section(
                restaurant_id, REFERRAL_REFEREE_CODE, db_alias=alias
            ),
        },
        "stamp": _stamp_section(restaurant_id),
    }


def format_coupon_benefits_summary_text(summary: dict) -> str:
    """관리·검수용 한 줄 요약 (coupon_benefits_summary 와 별도로 읽기 쉬운 텍스트)."""
    lines: list[str] = []

    signup = summary.get("signup") or {}
    if signup.get("excluded"):
        lines.append("[신규가입] 발급 제외")
    elif signup.get("items"):
        for item in signup["items"]:
            lines.append(f"[신규가입] {item.get('title', '')} {item.get('subtitle', '')}".strip())
    else:
        lines.append("[신규가입] 혜택 미등록")

    referral = summary.get("referral") or {}
    for role, label in (("referrer", "친구초대·추천인"), ("referee", "친구초대·피추천인")):
        block = referral.get(role) or {}
        if block.get("excluded"):
            lines.append(f"[{label}] 발급 제외")
        elif block.get("items"):
            for item in block["items"]:
                lines.append(f"[{label}] {item.get('title', '')} {item.get('subtitle', '')}".strip())
        else:
            lines.append(f"[{label}] 혜택 미등록")

    stamp = summary.get("stamp") or {}
    if not stamp.get("enabled"):
        note = (stamp.get("notes") or "").strip()
        lines.append("[스탬프] 미사용" + (f" — {note}" if note else ""))
        for reward in stamp.get("rewards") or []:
            if "stamps" in reward:
                lines.append(
                    f"[스탬프 표시 {reward['stamps']}개] {reward.get('title') or ''}".strip()
                )
    else:
        stamp_notes = (stamp.get("notes") or "").strip()
        if stamp_notes:
            lines.append(f"[스탬프 비고] {stamp_notes}")
        for reward in stamp.get("rewards") or []:
            if "stamps" in reward:
                prefix = f"{reward['stamps']}개"
            else:
                min_v = reward.get("min_visit")
                max_v = reward.get("max_visit")
                prefix = f"{min_v}~{max_v}회" if min_v != max_v else f"{min_v}회"
            title = reward.get("title") or ""
            notes = (reward.get("notes") or "").strip()
            line = f"[스탬프 {prefix}] {title}"
            if notes:
                line += f" ({notes})"
            lines.append(line)

    return "\n".join(lines)
