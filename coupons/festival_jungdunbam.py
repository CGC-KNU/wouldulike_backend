"""
우주라이크 X 정든밤 축제 주막(298) 데이터를 CloudSQL(restaurants_affiliate)에 반영.
마이그레이션·관리 명령에서 공통 사용.
"""
from __future__ import annotations

from datetime import datetime, time

from django.db import connections
from django.utils import timezone


RESTAURANT_ID = 298
MERCHANT_PIN = "0629"
RESTAURANT_NAME = "우주라이크 X 정든밤"
DESCRIPTION = (
    "경북대 80주년 축제 주막 · 스탬프 없음 · "
    "매주 수요일 앱 접속 시 음료수 1개 쿠폰 (기존 수요일 쿠폰과 별도)"
)
STAMP_DISABLED_NOTES = (
    "이 주막은 스탬프 적립·보상이 없습니다.\n"
    "오늘 하루만 운영되는 페이지입니다."
)
STAMP_DISABLED_RESTAURANT_IDS = frozenset({RESTAURANT_ID})
# 앱 제휴 목록 비노출 (쿠폰 발급·PIN·쿠폰함 사용은 유지)
IS_AFFILIATE_IN_APP = False
CATEGORY = "주점"
ZONE = "주막"
ADDRESS = "경북대학교 대구캠퍼스 80주년 축제 주막"

COUPON_TYPE_CODE = "JUNGDUNBAM_FESTIVAL_WED"
CAMPAIGN_CODE = "JUNGDUNBAM_FESTIVAL_WED_EVENT"
BENEFIT_TITLE = "음료수 1개"
BENEFIT_SUBTITLE = "[경북대 80주년 축제 🎉]"

FESTIVAL_START_KST = datetime(2026, 5, 1, 0, 0, 0)
FESTIVAL_END_KST = datetime(2026, 5, 31, 23, 59, 59)

COUPON_TYPES_TO_EXCLUDE = [
    "WELCOME_3000",
    "REFERRAL_BONUS_REFERRER",
    "REFERRAL_BONUS_REFEREE",
    "FINAL_EXAM_SPECIAL",
    "NEW_SEMESTER_SPECIAL",
    "KNULIKE",
    "DATELIKE",
    "FULL_AFFILIATE_SPECIAL",
    "APP_OPEN_MON",
    "APP_OPEN_WED",
    "DATE_EVENT_SPECIAL",
    "MIDTERM_EVENT_SPECIAL",
    "STAMP_REWARD_2",
    "STAMP_REWARD_3",
    "STAMP_REWARD_5",
    "STAMP_REWARD_6",
    "STAMP_REWARD_9",
    "STAMP_REWARD_10",
]


def wednesday_expires_at_kst(kst: datetime) -> datetime:
    """발급일(수요일) KST 23:59:59 — 당일 자정까지 사용."""
    return datetime.combine(kst.date(), time(23, 59, 59), tzinfo=kst.tzinfo)


def is_wednesday_kst(now=None) -> bool:
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    kst = (now or timezone.now()).astimezone(ZoneInfo("Asia/Seoul"))
    return kst.weekday() == 2


def _kst_aware(dt: datetime):
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    return dt.replace(tzinfo=ZoneInfo("Asia/Seoul"))


def resolve_cloudsql_alias() -> str:
    """앱 API와 동일하게 cloudsql 우선."""
    if "cloudsql" in connections.databases:
        return "cloudsql"
    return "default"


def is_stamp_disabled_restaurant(restaurant_id: int) -> bool:
    """단건 조회용 — 고정 ID만 (DB 왕복 없음). 배치는 stamp_disabled_restaurant_ids 사용."""
    return int(restaurant_id) in STAMP_DISABLED_RESTAURANT_IDS


def stamp_disabled_restaurant_ids(
    rule_map: dict[int, object] | None = None,
) -> set[int]:
    """rule_map 에서 stamp 비활성 식당 + 고정 ID 를 한 번에 수집."""
    disabled = set(STAMP_DISABLED_RESTAURANT_IDS)
    if not rule_map:
        return disabled
    for rid, rule in rule_map.items():
        config = getattr(rule, "config_json", None) or {}
        if stamp_rule_config_disables_stamps(config):
            disabled.add(int(rid))
    return disabled


def get_festival_promotions_for_app() -> list[dict]:
    """스탬프 대신 앱에 보여줄 축제 쿠폰 안내."""
    return [
        {
            "title": BENEFIT_TITLE,
            "subtitle": BENEFIT_SUBTITLE,
            "description": "매주 수요일 앱 접속 시 쿠폰함에 자동 발급",
            "coupon_type_code": COUPON_TYPE_CODE,
        }
    ]


def build_jungdunbam_stamp_rule_config() -> dict:
    """StampRewardRule.config_json — 프론트·API가 DB에서 읽는 스탬프 설정."""
    return {
        "stamp_enabled": False,
        "stamp_disabled": True,
        "legacy_stamp_defaults": False,
        "show_stamp_card": False,
        "thresholds": [],
        "cycle_target": None,
        "notes": STAMP_DISABLED_NOTES,
        "promotions": get_festival_promotions_for_app(),
    }


def stamp_rule_config_disables_stamps(config: dict | None) -> bool:
    if not config:
        return False
    if config.get("stamp_disabled") is True:
        return True
    if config.get("stamp_enabled") is False:
        return True
    return False


def build_stamp_disabled_api_payload(
    *,
    updated_at=None,
    rule_config: dict | None = None,
) -> dict:
    """
    스탬프 미사용 식당용 API 페이로드 (DB config_json 과 동일 필드).

    target/current 를 null 로 두어 프론트의 `target || 10` 레거시 폴백을 막는다.
    """
    cfg = rule_config if rule_config is not None else build_jungdunbam_stamp_rule_config()
    promotions = cfg.get("promotions")
    if promotions is None:
        promotions = get_festival_promotions_for_app()
    return {
        "current": None,
        "target": cfg.get("cycle_target"),
        "rewards": [],
        "notes": (cfg.get("notes") or STAMP_DISABLED_NOTES).strip(),
        "stamp_enabled": False,
        "legacy_stamp_defaults": bool(cfg.get("legacy_stamp_defaults", False)),
        "show_stamp_card": bool(cfg.get("show_stamp_card", False)),
        "promotions": promotions,
        "updated_at": updated_at,
    }


def ensure_stamp_disabled_rule_for_jungdunbam(*, db_alias: str) -> None:
    """
    스탬프 비활성 설정을 StampRewardRule 에 명시 (삭제하지 않음).
    STAMP_REWARD benefit 은 비활성화해 레거시 5·10개 혜택 문구가 붙지 않게 한다.
    """
    from coupons.models import RestaurantCouponBenefit, StampRewardRule

    StampRewardRule.objects.using(db_alias).update_or_create(
        restaurant_id=RESTAURANT_ID,
        defaults={
            "rule_type": "THRESHOLD",
            "config_json": build_jungdunbam_stamp_rule_config(),
            "active": True,
        },
    )
    RestaurantCouponBenefit.objects.using(db_alias).filter(
        restaurant_id=RESTAURANT_ID,
        coupon_type__code__startswith="STAMP_REWARD",
    ).update(active=False)


def disable_stamp_rewards_for_jungdunbam(*, db_alias: str) -> None:
    """하위 호환 alias."""
    ensure_stamp_disabled_rule_for_jungdunbam(db_alias=db_alias)


def upsert_affiliate_row(*, alias: str, pin: str, now) -> None:
    conn = connections[alias]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM restaurants_affiliate WHERE restaurant_id = %s",
            [RESTAURANT_ID],
        )
        exists = cursor.fetchone() is not None

    if exists:
        sql = """
            UPDATE restaurants_affiliate
            SET
              name = %s,
              is_affiliate = %s,
              description = %s,
              address = %s,
              category = %s,
              zone = %s,
              phone_number = NULL,
              url = NULL,
              pin_secret = %s,
              pin_updated_at = %s
            WHERE restaurant_id = %s
        """
        params = [
            RESTAURANT_NAME,
            IS_AFFILIATE_IN_APP,
            DESCRIPTION,
            ADDRESS,
            CATEGORY,
            ZONE,
            pin,
            now,
            RESTAURANT_ID,
        ]
    else:
        sql = """
            INSERT INTO restaurants_affiliate (
              restaurant_id, name, is_affiliate, description, address,
              category, zone, phone_number, url, s3_image_urls,
              pin_secret, pin_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s, %s)
        """
        params = [
            RESTAURANT_ID,
            RESTAURANT_NAME,
            IS_AFFILIATE_IN_APP,
            DESCRIPTION,
            ADDRESS,
            CATEGORY,
            ZONE,
            [],
            pin,
            now,
        ]

    with conn.cursor() as cursor:
        cursor.execute(sql, params)


def ensure_jungdunbam_festival_data(*, db_alias: str | None = None) -> str:
    """
    제휴 식당·PIN·수요일 쿠폰·exclusion 을 idempotent 하게 반영.
    반환: 사용한 DB alias.
    """
    from coupons.models import (
        Campaign,
        CouponRestaurantExclusion,
        CouponType,
        MerchantPin,
        RestaurantCouponBenefit,
    )
    from restaurants.models import AffiliateRestaurant

    alias = db_alias or resolve_cloudsql_alias()
    now = timezone.now()
    pin = MERCHANT_PIN
    start_at = _kst_aware(FESTIVAL_START_KST)
    end_at = _kst_aware(FESTIVAL_END_KST)

    upsert_affiliate_row(alias=alias, pin=pin, now=now)

    AffiliateRestaurant.objects.using(alias).update_or_create(
        restaurant_id=RESTAURANT_ID,
        defaults={
            "name": RESTAURANT_NAME,
            "is_affiliate": IS_AFFILIATE_IN_APP,
            "description": DESCRIPTION,
            "address": ADDRESS,
            "category": CATEGORY,
            "zone": ZONE,
            "phone_number": None,
            "url": None,
            "s3_image_urls": [],
            "pin_secret": pin,
            "pin_updated_at": now,
        },
    )

    MerchantPin.objects.using(alias).update_or_create(
        restaurant_id=RESTAURANT_ID,
        defaults={
            "algo": "STATIC",
            "secret": pin,
            "period_sec": 30,
            "last_rotated_at": now,
        },
    )

    CouponType.objects.using(alias).update_or_create(
        code=COUPON_TYPE_CODE,
        defaults={
            "title": "수요일 축제 주막 쿠폰",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 0},
        },
    )
    Campaign.objects.using(alias).update_or_create(
        code=CAMPAIGN_CODE,
        defaults={
            "name": "우주라이크 X 정든밤 축제 (수요일)",
            "type": "FLASH",
            "active": True,
            "start_at": start_at,
            "end_at": end_at,
            "rules_json": {},
        },
    )

    wed_ct = CouponType.objects.using(alias).get(code=COUPON_TYPE_CODE)
    RestaurantCouponBenefit.objects.using(alias).update_or_create(
        coupon_type=wed_ct,
        restaurant_id=RESTAURANT_ID,
        sort_order=0,
        defaults={
            "title": BENEFIT_TITLE,
            "subtitle": BENEFIT_SUBTITLE,
            "notes": "",
            "benefit_json": {"type": "fixed", "value": 0},
            "active": True,
        },
    )

    for code in COUPON_TYPES_TO_EXCLUDE:
        try:
            ct = CouponType.objects.using(alias).get(code=code)
        except CouponType.DoesNotExist:
            continue
        CouponRestaurantExclusion.objects.using(alias).update_or_create(
            coupon_type=ct,
            restaurant_id=RESTAURANT_ID,
            defaults={},
        )

    for ct in CouponType.objects.using(alias).filter(code__startswith="STAMP_REWARD"):
        if ct.code == COUPON_TYPE_CODE:
            continue
        CouponRestaurantExclusion.objects.using(alias).update_or_create(
            coupon_type=ct,
            restaurant_id=RESTAURANT_ID,
            defaults={},
        )

    ensure_stamp_disabled_rule_for_jungdunbam(db_alias=alias)

    return alias
