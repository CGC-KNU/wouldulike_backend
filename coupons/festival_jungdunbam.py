"""
우주라이크 X 정든밤 축제 주막(298) 데이터를 CloudSQL(restaurants_affiliate)에 반영.
마이그레이션·관리 명령에서 공통 사용.
"""
from __future__ import annotations

from datetime import datetime

from django.db import connections
from django.utils import timezone


RESTAURANT_ID = 298
MERCHANT_PIN = "0629"
RESTAURANT_NAME = "우주라이크 X 정든밤"
DESCRIPTION = "경북대 80주년 축제 주막"
CATEGORY = "주점"
ZONE = "주막"
ADDRESS = "경북대학교 대구캠퍼스 80주년 축제 주막"

COUPON_TYPE_CODE = "JUNGDUNBAM_FESTIVAL_WED"
CAMPAIGN_CODE = "JUNGDUNBAM_FESTIVAL_WED_EVENT"
BENEFIT_TITLE = "음료수 1개"
BENEFIT_SUBTITLE = "[🎪 축제 주막 쿠폰 🎪]"

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
              is_affiliate = TRUE,
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
            ) VALUES (%s, %s, TRUE, %s, %s, %s, %s, NULL, NULL, %s, %s, %s)
        """
        params = [
            RESTAURANT_ID,
            RESTAURANT_NAME,
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
            "is_affiliate": True,
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
            "valid_days": 3,
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

    return alias
