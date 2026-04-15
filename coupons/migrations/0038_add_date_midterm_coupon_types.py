from datetime import datetime, timezone

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


DATE_COUPON_TYPE_CODE = "DATE_EVENT_SPECIAL"
MIDTERM_COUPON_TYPE_CODE = "MIDTERM_EVENT_SPECIAL"
DATE_EVENT_APP_OPEN_CAMPAIGN_CODE = "DATE_EVENT_APP_OPEN"
MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE = "MIDTERM_EVENT_APP_OPEN"


DATE_BENEFITS = [
    {"name": "정든밤", "title": "콘튀김 증정"},
    {"name": "벨로", "title": "2인 이상 방문시 10% 할인"},
    {"name": "마름모식당", "title": "2인 주문시)\n작은 냉우동 제공"},
    {"name": "주비 두루 향기롭다", "title": "푸딩 1+1"},
    {"name": "난탄 경대북문점", "title": "하이볼 1+1"},
    {"name": "웃찌커피", "title": "5,000원 이상 주문시\n아메리카노 무료"},
    {"name": "하카타 파스타", "title": "고로케 제공"},
    {"name": "혜화문식당", "title": "인원수 맞게 새우튀김 서비스"},
]

MIDTERM_BENEFITS = [
    {"name": "통통주먹구이 경북대점", "title": "추억의 도시락"},
    {"name": "포차1번지먹새통 경북대점", "title": "프리미엄 메뉴 주문시\n미니빙수 제공"},
    {
        "name": "스톡홀롬샐러드 경대정문점",
        "title": "샐러드 구매시)\n- 아메리카노 기본사이즈 1,000원\n- 아메리카노 빅사이즈 1,000원",
    },
    {
        "name": "마름모식당",
        "title": "(현금결제 필수 / 쿠폰적립 제외)\n생연어덮밥 10,000원 식사권",
    },
    {"name": "주비 두루 향기롭다", "title": "우유 푸딩 테이크아웃 시\n아메리카노 500원"},
    {"name": "사랑과평화 경북대점", "title": "뻥튀기 아이스크림 제공"},
    {"name": "부리또익스프레스", "title": "감자튀김 제공"},
    {"name": "고씨네 대구경북대본점", "title": "인당 해시포테이토 1개"},
    {
        "name": "정직유부 경북대점",
        "title": "[17~20시 사용]\n9,000원 이상 결제시 (테이블 당)\n모든 유부 2P 제공",
    },
    {"name": "웃찌커피", "title": "아메리카노 / 라뗴 / 아이스티\n사이즈 업"},
    {"name": "기프트버거 경대점", "title": "갈릭버터 프라이즈 변경\n(버거 주문시)"},
    {"name": "다원국밥", "title": "고기 추가\n(방문시 - 소고기류 제외)"},
    {"name": "혜화문식당", "title": "인원수 맞게 새우튀김 서비스"},
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
    "대부 대왕유부초밥": 47,
    "부리또익스프레스": 41,
    "다이와스시": 56,
    "고씨네": 249,
    "혜화문식당": 245,
    "혜화문 식당": 245,
    "혜화문": 245,
}


def _normalize_name(value: str) -> str:
    return "".join((value or "").strip().split())


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
        benefit_model.objects.update_or_create(
            coupon_type=coupon_type,
            restaurant_id=restaurant_id,
            sort_order=0,
            defaults={
                "title": item["title"][:120],
                "subtitle": subtitle,
                "benefit_json": {},
                "notes": "",
                "active": True,
            },
        )

    benefit_model.objects.filter(coupon_type=coupon_type).exclude(
        restaurant_id__in=active_restaurant_ids
    ).update(active=False)


def add_date_midterm_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    date_type, _ = CouponType.objects.update_or_create(
        code=DATE_COUPON_TYPE_CODE,
        defaults={
            "title": "[데이트 기획전 쿠폰]",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {},
        },
    )
    midterm_type, _ = CouponType.objects.update_or_create(
        code=MIDTERM_COUPON_TYPE_CODE,
        defaults={
            "title": "[중간고사 기획전 쿠폰]",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {},
        },
    )

    # 2026-04-01 00:00:00 ~ 2026-04-12 23:59:59 (KST) 기간
    # UTC 저장값: 2026-03-31 15:00:00 ~ 2026-04-12 14:59:59
    Campaign.objects.update_or_create(
        code=DATE_EVENT_APP_OPEN_CAMPAIGN_CODE,
        defaults={
            "name": "데이트 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": True,
            "start_at": datetime(2026, 3, 31, 15, 0, 0, tzinfo=timezone.utc),
            "end_at": datetime(2026, 4, 12, 14, 59, 59, tzinfo=timezone.utc),
            "rules_json": {"trigger": "APP_OPEN"},
        },
    )
    Campaign.objects.update_or_create(
        code=MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE,
        defaults={
            "name": "중간고사 기획전 앱접속 쿠폰",
            "type": "FLASH",
            "active": False,
            "rules_json": {"trigger": "APP_OPEN"},
        },
    )

    try:
        restaurants = list(
            AffiliateRestaurant.objects.all().values("restaurant_id", "name")
        )
    except (OperationalError, ProgrammingError):
        # AffiliateRestaurant는 managed=False로, 로컬/테스트 DB에는 실제 테이블이 없을 수 있다.
        # 이 경우 혜택 시딩은 안전하게 스킵한다.
        return

    _upsert_benefits(
        coupon_type=date_type,
        subtitle="[데이트 기획전 쿠폰]",
        benefits=DATE_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )
    _upsert_benefits(
        coupon_type=midterm_type,
        subtitle="[중간고사 기획전 쿠폰]",
        benefits=MIDTERM_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )


def remove_date_midterm_coupon_types(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    for code in (DATE_COUPON_TYPE_CODE, MIDTERM_COUPON_TYPE_CODE):
        ct = CouponType.objects.filter(code=code).first()
        if not ct:
            continue
        RestaurantCouponBenefit.objects.filter(coupon_type=ct).delete()
        ct.delete()
    Campaign.objects.filter(
        code__in=(DATE_EVENT_APP_OPEN_CAMPAIGN_CODE, MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE)
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0037_update_app_open_mon_wed_subtitles"),
    ]

    operations = [
        migrations.RunPython(add_date_midterm_coupon_types, remove_date_midterm_coupon_types),
    ]
