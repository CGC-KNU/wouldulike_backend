from __future__ import annotations

from django.db import migrations
from django.utils import timezone


HACKBOB_NAME_KEYWORD = "핵밥"
HACKBOB_ADDRESS = "대구 북구 대학로 79 2층"
HACKBOB_PHONE_NUMBER = "0507-1337-6783"
HACKBOB_ZONE = "북문"
HACKBOB_CATEGORY = "한식"
HACKBOB_DESCRIPTION = "다양한 덮밥과 라멘 맛집!"
HACKBOB_NAVER_URL = "https://naver.me/G8s2Oz4q"
HACKBOB_PIN = "0306"
HACKBOB_IMAGE_URLS = [
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob1.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob2.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob3.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob4.jpeg",
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/hackbob/hackbob5.jpeg",
]


COUPON_TYPE_CODES = [
    "WELCOME_3000",
    "REFERRAL_BONUS_REFERRER",
    "REFERRAL_BONUS_REFEREE",
]

# CSV 기준 핵밥 쿠폰 4종
HACKBOB_AFFILIATE_COUPON_BENEFITS = [
    {
        "title": "닭튀김 2조각 (1인당)",
        "notes": "1인 1메뉴 주문 시",
    },
    {
        "title": "감자 고로케 증정 (2인 이상 방문시)",
        "notes": "1인 1메뉴 주문 시\n2인 이상 방문시",
    },
    {
        "title": "10% 할인 (3인 이상 / 현금 결제시)",
        "notes": "1인 1메뉴 주문 시\n3인 이상 / 현금 결제시",
    },
    {
        "title": "음료 택 1 (1인당)",
        "notes": "1인 1메뉴 주문 시",
    },
]


def _find_hackbob_restaurant_id(AffiliateRestaurant) -> int | None:
    """
    CloudSQL AffiliateRestaurant에서 '핵밥'에 해당하는 restaurant_id를 찾습니다.
    - 운영 환경에 따라 DB alias가 다를 수 있어 default → cloudsql 순으로 시도합니다.
    - 이름/주소 기반으로 최대한 정확히 매칭합니다.
    """
    candidates = []

    try:
        candidates = list(
            AffiliateRestaurant.objects.filter(name__icontains=HACKBOB_NAME_KEYWORD)[:20]
        )
    except Exception:
        candidates = []

    if not candidates:
        try:
            candidates = list(
                AffiliateRestaurant.objects.using("cloudsql").filter(
                    name__icontains=HACKBOB_NAME_KEYWORD
                )[:20]
            )
        except Exception:
            candidates = []

    if not candidates:
        return None

    # 주소가 이미 있으면 주소로 우선 매칭
    for r in candidates:
        addr = getattr(r, "address", None) or ""
        if HACKBOB_ADDRESS in addr:
            return int(r.restaurant_id)

    # 이름이 정확히 포함된 첫 후보 사용
    return int(candidates[0].restaurant_id)


def forward(apps, schema_editor):
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    MerchantPin = apps.get_model("coupons", "MerchantPin")
    StampRewardRule = apps.get_model("coupons", "StampRewardRule")

    restaurant_id = _find_hackbob_restaurant_id(AffiliateRestaurant)
    if not restaurant_id:
        # DB에 식당 row 자체가 없으면 여기서 생성/ID 할당은 위험하므로 스킵
        return

    # 1) 제휴식당 정보 업데이트 (restaurants_affiliate)
    now = timezone.now()
    try:
        # default 우선
        AffiliateRestaurant.objects.filter(restaurant_id=restaurant_id).update(
            is_affiliate=True,
            address=HACKBOB_ADDRESS,
            phone_number=HACKBOB_PHONE_NUMBER,
            zone=HACKBOB_ZONE,
            category=HACKBOB_CATEGORY,
            url=HACKBOB_NAVER_URL,
            s3_image_urls=HACKBOB_IMAGE_URLS,
            description=HACKBOB_DESCRIPTION,
            pin_secret=HACKBOB_PIN,
            pin_updated_at=now,
        )
    except Exception:
        try:
            AffiliateRestaurant.objects.using("cloudsql").filter(
                restaurant_id=restaurant_id
            ).update(
                is_affiliate=True,
                address=HACKBOB_ADDRESS,
                phone_number=HACKBOB_PHONE_NUMBER,
                zone=HACKBOB_ZONE,
                category=HACKBOB_CATEGORY,
                url=HACKBOB_NAVER_URL,
                s3_image_urls=HACKBOB_IMAGE_URLS,
                description=HACKBOB_DESCRIPTION,
                pin_secret=HACKBOB_PIN,
                pin_updated_at=now,
            )
        except Exception:
            # 제휴 식당 정보 업데이트 실패해도 쿠폰/스탬프 설정은 계속 시도
            pass

    # 2) PIN 반영 (coupons_merchantpin)
    try:
        MerchantPin.objects.update_or_create(
            restaurant_id=restaurant_id,
            defaults={
                "algo": "STATIC",
                "secret": HACKBOB_PIN,
                "period_sec": 30,
                "last_rotated_at": now,
            },
        )
    except Exception:
        try:
            MerchantPin.objects.using("cloudsql").update_or_create(
                restaurant_id=restaurant_id,
                defaults={
                    "algo": "STATIC",
                    "secret": HACKBOB_PIN,
                    "period_sec": 30,
                    "last_rotated_at": now,
                },
            )
        except Exception:
            pass

    # 3) 신규가입/친구초대 쿠폰 benefit 4종 등록
    for ct_code in COUPON_TYPE_CODES:
        try:
            ct = CouponType.objects.get(code=ct_code)
        except Exception:
            continue

        for sort_order, b in enumerate(HACKBOB_AFFILIATE_COUPON_BENEFITS):
            RestaurantCouponBenefit.objects.update_or_create(
                coupon_type=ct,
                restaurant_id=restaurant_id,
                sort_order=sort_order,
                defaults={
                    "title": b["title"],
                    "subtitle": "",
                    "notes": b["notes"],
                    # fixed 0: 실제 혜택은 식당에서 처리 (기존 제휴 쿠폰 패턴과 동일)
                    "benefit_json": {"type": "fixed", "value": 0},
                    "active": True,
                },
            )

    # 4) 스탬프 리워드 룰(3/5/10) + 스탬프 보상 쿠폰 benefit
    # - 룰은 StampRewardRule이 cloudsql DB를 사용하도록 서비스에서 고정되어 있으므로 cloudsql로 저장 시도
    stamp_rule_config = {
        "thresholds": [
            {"stamps": 3, "coupon_type_code": "STAMP_REWARD_3"},
            {"stamps": 5, "coupon_type_code": "STAMP_REWARD_5"},
            {"stamps": 10, "coupon_type_code": "STAMP_REWARD_10"},
        ],
        "cycle_target": 10,
        "notes": "테이블 당 1개 적립",
    }

    try:
        StampRewardRule.objects.using("cloudsql").update_or_create(
            restaurant_id=restaurant_id,
            defaults={
                "rule_type": "THRESHOLD",
                "config_json": stamp_rule_config,
                "active": True,
            },
        )
    except Exception:
        # cloudsql 연결이 없으면 스킵
        pass

    stamp_benefits = [
        ("STAMP_REWARD_3", "레몬 에이드"),
        ("STAMP_REWARD_5", "미니 돈가스"),
        ("STAMP_REWARD_10", "5,000원 할인"),
    ]
    for ct_code, title in stamp_benefits:
        try:
            ct = CouponType.objects.get(code=ct_code)
        except Exception:
            continue
        RestaurantCouponBenefit.objects.update_or_create(
            coupon_type=ct,
            restaurant_id=restaurant_id,
            sort_order=0,
            defaults={
                "title": title,
                "subtitle": "",
                "notes": "",
                "benefit_json": {},
                "active": True,
            },
        )


def backward(apps, schema_editor):
    # 운영 데이터 추가 마이그레이션은 원복(noop)이 안전합니다.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0051_make_medium_rare_event_timeboxed"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

