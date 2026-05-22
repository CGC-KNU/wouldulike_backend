"""
여름맞이·월드컵 기획전 CouponType 및 RestaurantCouponBenefit 시드.

CSV: 26-1 우주라이크 제휴 식당 - 캠페인별 참여 매장 및 한정쿠폰
- 여름맞이 (5/22~6/7)
- 월드컵 (6/8~6/21)

괄호로 표기된 조건은 title 이 아닌 notes(쿠폰 비고)에 저장한다.
"""
import re
from datetime import datetime, timezone

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


SUMMER_COUPON_TYPE_CODE = "SUMMER_EVENT_SPECIAL"
WORLD_CUP_COUPON_TYPE_CODE = "WORLD_CUP_EVENT_SPECIAL"
SUMMER_EVENT_APP_OPEN_CAMPAIGN_CODE = "SUMMER_EVENT_APP_OPEN"
WORLD_CUP_EVENT_APP_OPEN_CAMPAIGN_CODE = "WORLD_CUP_EVENT_APP_OPEN"

SUMMER_SUBTITLE = "[여름맞이 기획전 쿠폰 ☀️]"
WORLD_CUP_SUBTITLE = "[월드컵 기획전 쿠폰 ⚽]"

SUMMER_BENEFITS = [
    {"name": "통통주먹구이 경북대점", "title": "물냉면"},
    {"name": "벨로", "title": "2인 이상 방문시 10% 할인"},
    {"name": "닭동가리 경북대점", "title": "팥빙수 or 파인샤베트 택 1"},
    {
        "name": "정직유부 경북대점",
        "title": "냉모밀/초계면 주문시\n메뉴당 1개\n맛보기 유부 1알 제공",
    },
    {"name": "웃찌커피", "title": "생과일 주스 사이즈 업"},
    {"name": "하카타 파스타", "title": "고로케 제공"},
    {
        "name": "기프트버거 경대점",
        "title": "밀크셰이크 제공",
        "notes": "12,000원 결제시",
    },
    {"name": "다원국밥", "title": "만두 2P", "notes": "냉면 주문시"},
    {
        "name": "핵밥 경북대점",
        "title": "냉소바, 자루소바, 붓카케우동 주문 후 현금결제시 10% 할인",
        "notes": "단품/세트 무관",
    },
]

WORLD_CUP_BENEFITS = [
    {"name": "정든밤", "title": "소주 1병 증정"},
    {
        "name": "구구포차 본점",
        "title": "치킨/통닭 랜덤 제공",
        "notes": "8인 이하, 중복이벤트 불가, 리뷰이벤트 참여시",
    },
    {
        "name": "포차1번지먹새통 경북대점",
        "title": "프리미엄 메뉴 주문시\n피카츄 돈가스 2마리 제공",
        "notes": "주류 주문 필수",
    },
    {"name": "닭동가리 경북대점", "title": "팥빙수 or 파인샤베트 택 1"},
    {"name": "북성로우동불고기", "title": "사이드 매뉴 택 1"},
    {"name": "난탄 경대북문점", "title": "생맥주 1+1"},
    {"name": "사랑과평화 경북대점", "title": "뻥튀기 아이스크림 제공"},
    {"name": "부리또익스프레스", "title": "감자튀김 제공"},
    {
        "name": "핵밥 경북대점",
        "title": "덮밥 주문시 미니우동 제공",
        "notes": "단품",
    },
]

NAME_TO_ID = {
    "정든밤": 97,
    "구구포차": 33,
    "통통주먹구이": 145,
    "포차1번지먹새통": 147,
    "스톡홀름샐러드": 143,
    "스톡홀롬샐러드": 143,
    "벨로": 19,
    "닭동가리": 146,
    "마름모식당": 62,
    "주비두루": 144,
    "주비 두루": 144,
    "북성로우동불고기": 266,
    "북성로 우동 불고기": 266,
    "난탄": 285,
    "사랑과평화": 271,
    "한끼갈비": 74,
    "고니식탁": 30,
    "대부": 47,
    "부리또익스프레스": 41,
    "다이와스시": 56,
    "고씨네": 249,
    "혜화문식당": 245,
    "혜화문 식당": 245,
    "혜화문": 245,
}


def _normalize_name(value: str) -> str:
    return "".join((value or "").strip().split())


def _split_paren_to_notes(text: str) -> tuple[str, str]:
    """
    title 문자열에서 괄호 조건을 notes 로 분리.
    - 줄 전체가 (조건) 형태이면 notes 로만 사용
    - 인라인 (조건) 은 title 에서 제거 후 notes 에 합침
    """
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
    """item 의 title/notes 를 정규화. notes 가 있으면 title 에 남은 괄호도 추가 분리."""
    explicit_notes = (item.get("notes") or "").strip()
    base_title = (item.get("title") or "").strip()
    parsed_title, parsed_notes = _split_paren_to_notes(base_title)

    note_chunks = [n for n in (parsed_notes, explicit_notes) if n]
    notes = "\n".join(note_chunks).strip()
    return parsed_title[:120], notes[:500]


def _resolve_restaurant_id(name: str, all_restaurants: list[dict]) -> int | None:
    normalized = _normalize_name(name)

    for key, restaurant_id in NAME_TO_ID.items():
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


def add_summer_worldcup_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    summer_type, _ = CouponType.objects.update_or_create(
        code=SUMMER_COUPON_TYPE_CODE,
        defaults={
            "title": SUMMER_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {},
        },
    )
    world_cup_type, _ = CouponType.objects.update_or_create(
        code=WORLD_CUP_COUPON_TYPE_CODE,
        defaults={
            "title": WORLD_CUP_SUBTITLE,
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {},
        },
    )

    # 2026-05-22 00:00:00 ~ 2026-06-07 23:59:59 (KST)
    summer_start = datetime(2026, 5, 21, 15, 0, 0, tzinfo=timezone.utc)
    summer_end = datetime(2026, 6, 7, 14, 59, 59, tzinfo=timezone.utc)
    # 2026-06-08 00:00:00 ~ 2026-06-21 23:59:59 (KST)
    world_cup_start = datetime(2026, 6, 7, 15, 0, 0, tzinfo=timezone.utc)
    world_cup_end = datetime(2026, 6, 21, 14, 59, 59, tzinfo=timezone.utc)

    Campaign.objects.update_or_create(
        code=SUMMER_EVENT_APP_OPEN_CAMPAIGN_CODE,
        defaults={
            "name": "여름맞이 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": False,
            "start_at": summer_start,
            "end_at": summer_end,
            "rules_json": {"trigger": "APP_OPEN"},
        },
    )
    Campaign.objects.update_or_create(
        code=WORLD_CUP_EVENT_APP_OPEN_CAMPAIGN_CODE,
        defaults={
            "name": "월드컵 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": False,
            "start_at": world_cup_start,
            "end_at": world_cup_end,
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
        coupon_type=summer_type,
        subtitle=SUMMER_SUBTITLE,
        benefits=SUMMER_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )
    _upsert_benefits(
        coupon_type=world_cup_type,
        subtitle=WORLD_CUP_SUBTITLE,
        benefits=WORLD_CUP_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )


def remove_summer_worldcup_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    for code in (SUMMER_COUPON_TYPE_CODE, WORLD_CUP_COUPON_TYPE_CODE):
        ct = CouponType.objects.filter(code=code).first()
        if not ct:
            continue
        RestaurantCouponBenefit.objects.filter(coupon_type=ct).delete()
        ct.delete()
    Campaign.objects.filter(
        code__in=(
            SUMMER_EVENT_APP_OPEN_CAMPAIGN_CODE,
            WORLD_CUP_EVENT_APP_OPEN_CAMPAIGN_CODE,
        )
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0077_jungdunbam_is_affiliate_false"),
    ]

    operations = [
        migrations.RunPython(
            add_summer_worldcup_coupon_types,
            remove_summer_worldcup_coupon_types,
        ),
    ]
