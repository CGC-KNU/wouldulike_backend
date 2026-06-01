"""
우주라이크 X 정든밤 축제 주막(restaurant_id=299) 데이터를 CloudSQL에 반영.
마이그레이션·관리 명령에서 공통 사용.
"""
from __future__ import annotations

from datetime import datetime

from django.db import connections
from django.utils import timezone


RESTAURANT_ID = 299
# 축제 주막이 잠시 쓰던 ID(현재 슈퍼크리스피 경북대점). reassign 시에만 사용.
LEGACY_FESTIVAL_RESTAURANT_ID = 298
MERCHANT_PIN = "0629"
RESTAURANT_NAME = "우주라이크 X 정든밤"
DESCRIPTION = (
    "경북대 80주년 축제 주막 · 스탬프 없음 · "
    "5/20 23:59(KST)까지 앱 접속 시 음료수 1개 쿠폰 (기존 수요일 쿠폰과 별도)"
)
STAMP_DISABLED_NOTES = (
    "이 주막은 스탬프 적립, 보상이 없습니다.\n"
    "오늘 하루만 운영되는 페이지입니다."
)
# 앱 스탬프 카드 표시용 (실제 적립·쿠폰 발급 없음)
FESTIVAL_STAMP_CYCLE_TARGET = 10
FESTIVAL_STAMP_DISPLAY_THRESHOLDS = (5, 10)
STAMP_DISPLAY_NO_REWARD_MESSAGE = "이 주막은 스탬프 적립, 보상이 없습니다."
# 레거시 앱: `스탬프 N개 적립 시 {title} 제공` 템플릿용 (괄호로 문장만 전달)
STAMP_DISPLAY_REWARD_TITLE_LEGACY = f"({STAMP_DISPLAY_NO_REWARD_MESSAGE})"
STAMP_BENEFIT_DISPLAY_PLAIN = {
    "mode": "plain",
    "text": STAMP_DISPLAY_NO_REWARD_MESSAGE,
}
STAMP_DISABLED_RESTAURANT_IDS = frozenset({RESTAURANT_ID})


def festival_restaurant_ids_excluded_from_pub_pools() -> frozenset[int]:
    """수요일 APP_OPEN_WED·주점 이벤트 등 술집/주점 풀에서 제외 (축제 전용 발급만)."""
    return STAMP_DISABLED_RESTAURANT_IDS
# 앱 제휴 식당 탭·넘기기 목록 비노출 (쿠폰·PIN·상세는 restaurant_id로 유지)
IS_AFFILIATE_IN_APP = False
CATEGORY = "주점"
ZONE = "주막"
ADDRESS = "경북대학교 대구캠퍼스 80주년 축제 주막"

COUPON_TYPE_CODE = "JUNGDUNBAM_FESTIVAL_WED"
CAMPAIGN_CODE = "JUNGDUNBAM_FESTIVAL_WED_EVENT"
BENEFIT_TITLE = "음료수 1개"
BENEFIT_SUBTITLE = "[경북대 80주년 축제 🎉]"

FESTIVAL_START_KST = datetime(2026, 5, 1, 0, 0, 0)
# 앱 접속 발급·쿠폰 만료 공통 마감 (KST)
FESTIVAL_APP_OPEN_END_KST = datetime(2026, 5, 20, 23, 59, 59)
FESTIVAL_END_KST = FESTIVAL_APP_OPEN_END_KST

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
    "PUB_JUJEOM_EVENT",
    "STAMP_REWARD_2",
    "STAMP_REWARD_3",
    "STAMP_REWARD_5",
    "STAMP_REWARD_6",
    "STAMP_REWARD_9",
    "STAMP_REWARD_10",
]


def festival_coupon_expires_at_kst() -> datetime:
    """축제 주막 쿠폰 만료: 5/20 23:59:59 KST."""
    return _kst_aware(FESTIVAL_APP_OPEN_END_KST)


def is_festival_app_open_issue_period(now=None) -> bool:
    """5/20 23:59(KST)까지 앱 접속 시 발급 가능."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    kst = (now or timezone.now()).astimezone(ZoneInfo("Asia/Seoul"))
    start = _kst_aware(FESTIVAL_START_KST)
    end = _kst_aware(FESTIVAL_APP_OPEN_END_KST)
    return start <= kst <= end


def wednesday_expires_at_kst(kst: datetime) -> datetime:
    """하위 호환 — 만료는 항상 축제 마감일."""
    return festival_coupon_expires_at_kst()


def is_wednesday_kst(now=None) -> bool:
    """deprecated: 발급 요일 제한 없음."""
    return is_festival_app_open_issue_period(now)


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
            "description": "5월 20일 23:59(KST)까지 앱 접속 시 쿠폰함에 자동 발급",
            "coupon_type_code": COUPON_TYPE_CODE,
        }
    ]


def get_festival_display_stamp_rewards() -> list[dict]:
    """
    스탬프 카드 UI용 5·10개 구간 — 실제 보상·적립 없음(display_only).

    - label / reward_label: 앱이 plain 모드일 때 그대로 표시
    - title: 레거시 `스탬프 N개 적립 시 {title} 제공` 템플릿용 (괄호 문구)
    """
    return [
        {
            "stamps": stamps,
            "title": STAMP_DISPLAY_REWARD_TITLE_LEGACY,
            "label": STAMP_DISPLAY_NO_REWARD_MESSAGE,
            "reward_label": STAMP_DISPLAY_NO_REWARD_MESSAGE,
            "subtitle": "",
            "notes": "",
            "benefit": {},
            "display_only": True,
            "render_mode": "plain",
        }
        for stamps in FESTIVAL_STAMP_DISPLAY_THRESHOLDS
    ]


def build_jungdunbam_stamp_rule_config() -> dict:
    """StampRewardRule.config_json — 프론트·API가 DB에서 읽는 스탬프 설정."""
    return {
        "stamp_enabled": False,
        "stamp_disabled": True,
        "legacy_stamp_defaults": False,
        "show_stamp_card": True,
        "cycle_target": FESTIVAL_STAMP_CYCLE_TARGET,
        "thresholds": [
            {"stamps": stamps, "display_only": True}
            for stamps in FESTIVAL_STAMP_DISPLAY_THRESHOLDS
        ],
        "display_rewards": get_festival_display_stamp_rewards(),
        "stamp_benefit_display": dict(STAMP_BENEFIT_DISPLAY_PLAIN),
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

    display_rewards 가 있으면 5·10 등 구간을 보여주되 적립은 stamp_enabled=false 로 막는다.
    """
    cfg = rule_config if rule_config is not None else build_jungdunbam_stamp_rule_config()
    promotions = cfg.get("promotions")
    if promotions is None:
        promotions = get_festival_promotions_for_app()
    display_rewards = cfg.get("display_rewards")
    if display_rewards is None and cfg.get("show_stamp_card"):
        display_rewards = get_festival_display_stamp_rewards()
    display_rewards = display_rewards or []
    cycle_target = cfg.get("cycle_target")
    show_card = bool(cfg.get("show_stamp_card", False))
    use_stamp_card = show_card and bool(display_rewards)
    stamp_benefit_display = cfg.get("stamp_benefit_display")
    if stamp_benefit_display is None and use_stamp_card:
        stamp_benefit_display = dict(STAMP_BENEFIT_DISPLAY_PLAIN)
    payload = {
        "current": 0 if use_stamp_card else None,
        "target": cycle_target if use_stamp_card else cfg.get("cycle_target"),
        "rewards": display_rewards,
        "notes": (cfg.get("notes") or STAMP_DISABLED_NOTES).strip(),
        "stamp_enabled": False,
        "legacy_stamp_defaults": bool(cfg.get("legacy_stamp_defaults", False)),
        "show_stamp_card": show_card,
        "promotions": promotions,
        "updated_at": updated_at,
    }
    if stamp_benefit_display:
        payload["stamp_benefit_display"] = stamp_benefit_display
    return payload


def _reassign_restaurant_coupon_benefits(
    *, alias: str, old_id: int, new_id: int
) -> None:
    from coupons.models import RestaurantCouponBenefit

    new_keys = set(
        RestaurantCouponBenefit.objects.using(alias)
        .filter(restaurant_id=new_id)
        .values_list("coupon_type_id", "sort_order")
    )
    old_benefits = list(
        RestaurantCouponBenefit.objects.using(alias).filter(restaurant_id=old_id)
    )
    for benefit in old_benefits:
        key = (benefit.coupon_type_id, benefit.sort_order)
        if key in new_keys:
            benefit.delete()
        else:
            benefit.restaurant_id = new_id
            benefit.save(update_fields=["restaurant_id"])
            new_keys.add(key)


def _reassign_coupon_restaurant_exclusions(
    *, alias: str, old_id: int, new_id: int
) -> None:
    from coupons.models import CouponRestaurantExclusion

    new_type_ids = set(
        CouponRestaurantExclusion.objects.using(alias)
        .filter(restaurant_id=new_id)
        .values_list("coupon_type_id", flat=True)
    )
    for row in CouponRestaurantExclusion.objects.using(alias).filter(
        restaurant_id=old_id
    ):
        if row.coupon_type_id in new_type_ids:
            row.delete()
        else:
            row.restaurant_id = new_id
            row.save(update_fields=["restaurant_id"])
            new_type_ids.add(row.coupon_type_id)


def _reassign_stamp_wallets(*, alias: str, old_id: int, new_id: int) -> None:
    from coupons.models import StampEvent, StampWallet

    for wallet in StampWallet.objects.using(alias).filter(restaurant_id=old_id):
        existing = (
            StampWallet.objects.using(alias)
            .filter(user_id=wallet.user_id, restaurant_id=new_id)
            .first()
        )
        if existing:
            existing.stamps = (existing.stamps or 0) + (wallet.stamps or 0)
            existing.save(update_fields=["stamps"])
            StampEvent.objects.using(alias).filter(
                user_id=wallet.user_id, restaurant_id=old_id
            ).update(restaurant_id=new_id)
            wallet.delete()
        else:
            wallet.restaurant_id = new_id
            wallet.save(update_fields=["restaurant_id"])


def reassign_festival_restaurant_id(
    *,
    db_alias: str,
    old_id: int = LEGACY_FESTIVAL_RESTAURANT_ID,
    new_id: int = RESTAURANT_ID,
) -> None:
    """축제 주막 restaurant_id 를 old_id → new_id 로 이전하고 구 ID 는 제휴 해제."""
    if old_id == new_id:
        ensure_jungdunbam_festival_data(db_alias=db_alias)
        return

    from coupons.models import (
        Coupon,
        MerchantPin,
        StampEvent,
        StampRewardRule,
    )
    from restaurants.models import AffiliateRestaurant

    alias = db_alias

    Coupon.objects.using(alias).filter(restaurant_id=old_id).update(
        restaurant_id=new_id
    )
    StampEvent.objects.using(alias).filter(restaurant_id=old_id).update(
        restaurant_id=new_id
    )

    _reassign_restaurant_coupon_benefits(alias=alias, old_id=old_id, new_id=new_id)
    _reassign_coupon_restaurant_exclusions(alias=alias, old_id=old_id, new_id=new_id)
    _reassign_stamp_wallets(alias=alias, old_id=old_id, new_id=new_id)

    if StampRewardRule.objects.using(alias).filter(restaurant_id=new_id).exists():
        StampRewardRule.objects.using(alias).filter(restaurant_id=old_id).delete()
    else:
        StampRewardRule.objects.using(alias).filter(restaurant_id=old_id).update(
            restaurant_id=new_id
        )

    if MerchantPin.objects.using(alias).filter(restaurant_id=new_id).exists():
        MerchantPin.objects.using(alias).filter(restaurant_id=old_id).delete()
    else:
        MerchantPin.objects.using(alias).filter(restaurant_id=old_id).update(
            restaurant_id=new_id
        )

    if AffiliateRestaurant.objects.using(alias).filter(restaurant_id=old_id).exists():
        AffiliateRestaurant.objects.using(alias).filter(restaurant_id=old_id).update(
            is_affiliate=False
        )

    conn = connections[alias]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM restaurants_affiliate WHERE restaurant_id = %s",
            [new_id],
        )
        new_exists = cursor.fetchone() is not None
        cursor.execute(
            "SELECT 1 FROM restaurants_affiliate WHERE restaurant_id = %s",
            [old_id],
        )
        old_exists = cursor.fetchone() is not None
        if old_exists and not new_exists:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET restaurant_id = %s
                WHERE restaurant_id = %s
                """,
                [new_id, old_id],
            )
        elif old_exists and new_exists:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET is_affiliate = FALSE
                WHERE restaurant_id = %s
                """,
                [old_id],
            )

    ensure_jungdunbam_festival_data(db_alias=alias)

    from coupons.models import RestaurantCouponBenefit

    RestaurantCouponBenefit.objects.using(alias).filter(restaurant_id=old_id).update(
        active=False
    )


def deactivate_non_festival_coupon_benefits(*, db_alias: str) -> None:
    """축제 주막: 음료 쿠폰 benefit 만 남기고 나머지 식당 benefit 비활성화."""
    from coupons.models import RestaurantCouponBenefit

    RestaurantCouponBenefit.objects.using(db_alias).filter(
        restaurant_id=RESTAURANT_ID,
    ).exclude(coupon_type__code=COUPON_TYPE_CODE).update(active=False)


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
    제휴 식당·PIN·앱 접속 쿠폰(5/20 마감)·exclusion 을 idempotent 하게 반영.
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
            "title": "축제 주막 앱 접속 쿠폰",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 0},
        },
    )
    Campaign.objects.using(alias).update_or_create(
        code=CAMPAIGN_CODE,
        defaults={
            "name": "우주라이크 X 정든밤 축제 (앱 접속)",
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
    deactivate_non_festival_coupon_benefits(db_alias=alias)

    return alias
