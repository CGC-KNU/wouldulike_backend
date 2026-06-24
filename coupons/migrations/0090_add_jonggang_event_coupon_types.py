"""
종강 기획전 CouponType 및 RestaurantCouponBenefit 시드.

CSV: 26-1 우주라이크 제휴 식당 - 캠페인별 참여 매장 및 한정쿠폰
- 종강 (6/22~7/7)
"""
import re
from datetime import datetime, timezone

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


JONGGANG_COUPON_TYPE_CODE = "JONGGANG_EVENT_SPECIAL"
JONGGANG_EVENT_APP_OPEN_CAMPAIGN_CODE = "JONGGANG_EVENT_APP_OPEN"
JONGGANG_SUBTITLE = "[종강 기획전 쿠폰 🎓]"

JONGGANG_BENEFITS = [
    {"name": "정든밤", "title": "얼음황도 증정"},
    {
        "name": "구구포차 본점",
        "title": "치킨/통닭 랜덤 제공",
        "notes": "8인 이하, 중복이벤트 불가, 리뷰이벤트 참여시",
    },
    {"name": "닭동가리 경북대점", "title": "팥빙수 or 파인샤베트 택 1"},
    {"name": "북성로우동불고기", "title": "사이드 메뉴 택 1"},
    {"name": "난탄 경대북문점", "title": "소주, 맥주 택 1"},
    {"name": "사랑과평화 경북대점", "title": "뻥튀기 아이스크림 제공"},
    {"name": "핵밥 경북대점", "title": "전메뉴 10% 할인 (현금결제시)"},
]

NAME_TO_ID = {
    "정든밤": 97,
    "구구포차": 33,
    "닭동가리": 146,
    "북성로우동불고기": 266,
    "북성로 우동 불고기": 266,
    "난탄": 285,
    "사랑과평화": 271,
    "핵밥": None,
}


def _normalize_name(value: str) -> str:
    return "".join((value or "").strip().split())


def _split_paren_to_notes(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", ""

    note_parts: list[str] = []
    title_lines: list[str] = []

    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"\((.+)\)", line):
            note_parts.append(re.fullmatch(r"\((.+)\)", line).group(1).strip())
            continue
        for match in re.finditer(r"\(([^)]+)\)", line):
            note_parts.append(match.group(1).strip())
        cleaned = re.sub(r"\s*\([^)]+\)\s*", " ", line)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            title_lines.append(cleaned)

    title = "\n".join(title_lines).strip()
    notes = "\n".join(note_parts).strip()
    return title, notes


def _resolve_title_notes(item: dict) -> tuple[str, str]:
    explicit_notes = (item.get("notes") or "").strip()
    base_title = (item.get("title") or "").strip()
    parsed_title, parsed_notes = _split_paren_to_notes(base_title)

    note_chunks = [n for n in (parsed_notes, explicit_notes) if n]
    notes = "\n".join(note_chunks).strip()
    return parsed_title[:120], notes[:500]


def _resolve_restaurant_id(name: str, all_restaurants: list[dict]) -> int | None:
    normalized = _normalize_name(name)

    for key, restaurant_id in NAME_TO_ID.items():
        if restaurant_id is None:
            continue
        key_norm = _normalize_name(key)
        if key_norm in normalized or normalized in key_norm:
            return restaurant_id

    for row in all_restaurants:
        db_name = row["name"] or ""
        db_norm = _normalize_name(db_name)
        if not db_norm:
            continue
        if db_norm in normalized or normalized in db_norm:
            return row["restaurant_id"]
    return None


def _upsert_benefits(*, coupon_type, subtitle: str, benefits: list[dict], all_restaurants, benefit_model):
    active_restaurant_ids: set[int] = set()

    for item in benefits:
        restaurant_id = _resolve_restaurant_id(item["name"], all_restaurants)
        if restaurant_id is None:
            continue
        active_restaurant_ids.add(restaurant_id)
        title, notes = _resolve_title_notes(item)
        benefit_model.objects.update_or_create(
            coupon_type=coupon_type,
            restaurant_id=restaurant_id,
            sort_order=0,
            defaults={
                "title": title,
                "subtitle": subtitle,
                "benefit_json": {},
                "notes": notes,
                "active": True,
            },
        )

    benefit_model.objects.filter(coupon_type=coupon_type).exclude(
        restaurant_id__in=active_restaurant_ids
    ).update(active=False)


def add_jonggang_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    jonggang_type, _ = CouponType.objects.update_or_create(
        code=JONGGANG_COUPON_TYPE_CODE,
        defaults={
            "title": JONGGANG_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {},
        },
    )

    # 2026-06-22 00:00:00 ~ 2026-07-07 23:59:59 (KST)
    jonggang_start = datetime(2026, 6, 21, 15, 0, 0, tzinfo=timezone.utc)
    jonggang_end = datetime(2026, 7, 7, 14, 59, 59, tzinfo=timezone.utc)

    Campaign.objects.update_or_create(
        code=JONGGANG_EVENT_APP_OPEN_CAMPAIGN_CODE,
        defaults={
            "name": "종강 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": False,
            "start_at": jonggang_start,
            "end_at": jonggang_end,
            "rules_json": {"trigger": "APP_OPEN"},
        },
    )

    try:
        restaurants = list(
            AffiliateRestaurant.objects.all().values("restaurant_id", "name")
        )
    except (OperationalError, ProgrammingError):
        return

    _upsert_benefits(
        coupon_type=jonggang_type,
        subtitle=JONGGANG_SUBTITLE,
        benefits=JONGGANG_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )


def remove_jonggang_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    ct = CouponType.objects.filter(code=JONGGANG_COUPON_TYPE_CODE).first()
    if ct:
        RestaurantCouponBenefit.objects.filter(coupon_type=ct).delete()
        ct.delete()
    Campaign.objects.filter(code=JONGGANG_EVENT_APP_OPEN_CAMPAIGN_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0089_add_world_cup_partner_bulk_event"),
    ]

    operations = [
        migrations.RunPython(add_jonggang_coupon_types, remove_jonggang_coupon_types),
    ]
