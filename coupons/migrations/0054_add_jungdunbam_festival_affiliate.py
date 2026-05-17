"""
우주라이크 X 정든밤(경북대 80주년 축제 주막) 제휴 등록 및 수요일 전용 음료 쿠폰.

- restaurants_affiliate: restaurant_id=298, is_affiliate=True
- CouponType JUNGDUNBAM_FESTIVAL_WED + Campaign (축제 기간)
- 다른 쿠폰 타입 발급 제외(CouponRestaurantExclusion + service RESTAURANTS_EXCLUDED_FROM_ALL)
- 스탬프 미사용(StampRewardRule/benefit 없음)
"""
from __future__ import annotations

from datetime import datetime

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError
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

# 축제 운영 기간 (KST) — 종료 후 Campaign.active=False 로도 중지 가능
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


def _upsert_affiliate_on_connection(conn, *, pin: str, now) -> None:
    """restaurants_affiliate 행을 INSERT 또는 UPDATE."""
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
              restaurant_id,
              name,
              is_affiliate,
              description,
              address,
              category,
              zone,
              phone_number,
              url,
              s3_image_urls,
              pin_secret,
              pin_updated_at
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
        try:
            cursor.execute(sql, params)
        except (OperationalError, ProgrammingError):
            # s3_image_urls 컬럼 없는 환경 폴백
            if not exists:
                cursor.execute(
                    """
                    INSERT INTO restaurants_affiliate (
                      restaurant_id, name, is_affiliate, description,
                      address, category, zone, phone_number, url,
                      pin_secret, pin_updated_at
                    ) VALUES (%s, %s, TRUE, %s, %s, %s, %s, NULL, NULL, %s, %s)
                    """,
                    [
                        RESTAURANT_ID,
                        RESTAURANT_NAME,
                        DESCRIPTION,
                        ADDRESS,
                        CATEGORY,
                        ZONE,
                        pin,
                        now,
                    ],
                )
            else:
                raise


def forward(apps, schema_editor):
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign = apps.get_model("coupons", "Campaign")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    CouponRestaurantExclusion = apps.get_model("coupons", "CouponRestaurantExclusion")
    MerchantPin = apps.get_model("coupons", "MerchantPin")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    now = timezone.now()
    pin = MERCHANT_PIN
    start_at = _kst_aware(FESTIVAL_START_KST)
    end_at = _kst_aware(FESTIVAL_END_KST)

    # 1) CloudSQL / default 연결에 제휴 식당 반영
    conn = schema_editor.connection
    try:
        _upsert_affiliate_on_connection(conn, pin=pin, now=now)
    except Exception:
        pass

    for db_alias in ("cloudsql", "default"):
        try:
            AffiliateRestaurant.objects.using(db_alias).update_or_create(
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
        except Exception:
            continue

    # 2) 쿠폰 리딤용 PIN
    for db_alias in ("default", "cloudsql"):
        try:
            MerchantPin.objects.using(db_alias).update_or_create(
                restaurant_id=RESTAURANT_ID,
                defaults={
                    "algo": "STATIC",
                    "secret": pin,
                    "period_sec": 30,
                    "last_rotated_at": now,
                },
            )
        except Exception:
            continue

    # 3) 수요일 전용 CouponType / Campaign
    CouponType.objects.update_or_create(
        code=COUPON_TYPE_CODE,
        defaults={
            "title": "수요일 축제 주막 쿠폰",
            "valid_days": 3,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 0},
        },
    )
    Campaign.objects.update_or_create(
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

    wed_ct = CouponType.objects.get(code=COUPON_TYPE_CODE)
    RestaurantCouponBenefit.objects.update_or_create(
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

    # 4) 다른 발급 경로 제외
    for code in COUPON_TYPES_TO_EXCLUDE:
        try:
            ct = CouponType.objects.get(code=code)
        except CouponType.DoesNotExist:
            continue
        CouponRestaurantExclusion.objects.update_or_create(
            coupon_type=ct,
            restaurant_id=RESTAURANT_ID,
            defaults={},
        )

    # STAMP_REWARD_* 전부 제외 (목록에 없는 확장 코드 대비)
    for ct in CouponType.objects.filter(code__startswith="STAMP_REWARD"):
        if ct.code == COUPON_TYPE_CODE:
            continue
        CouponRestaurantExclusion.objects.update_or_create(
            coupon_type=ct,
            restaurant_id=RESTAURANT_ID,
            defaults={},
        )


def backward(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0053_fix_hackbob_phone_and_images_on_cloudsql"),
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
