import uuid
import random
import logging
import os
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, time
from django.db import transaction, IntegrityError, router, DatabaseError
from django.db.models import Count, Sum
from utils.db_locks import locked_get
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from restaurants.models import AffiliateRestaurant

from .models import (
    Campaign,
    CouponType,
    Coupon,
    InviteCode,
    Referral,
    MerchantPin,
    StampWallet,
    StampEvent,
    StampRewardRule,
    RestaurantCouponBenefit,
    CouponRestaurantExclusion,
)
from .utils import make_coupon_code, redis_lock, idem_get, idem_set


User = get_user_model()

logger = logging.getLogger(__name__)


GLOBAL_COUPON_EXPIRY = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)
# 데이트 기획전 쿠폰 만료일 (2026-04-12 23:59:59 KST = 2026-04-12 14:59:59 UTC)
DATE_EVENT_COUPON_EXPIRES_AT = datetime(2026, 4, 12, 14, 59, 59, tzinfo=timezone.utc)
# 중간고사 기획전 쿠폰 만료일 (2026-04-24 23:59:59 KST = 2026-04-24 14:59:59 UTC)
MIDTERM_EVENT_COUPON_EXPIRES_AT = datetime(2026, 4, 24, 14, 59, 59, tzinfo=timezone.utc)
REFERRAL_MAX_REWARDS_PER_REFERRER = 5

# 운영진 계정 카카오 ID 목록 (환경 변수에서 읽어옴, 쉼표로 구분)
EVENT_ADMIN_KAKAO_IDS = set(
    int(kid.strip())
    for kid in os.getenv("EVENT_ADMIN_KAKAO_IDS", "").split(",")
    if kid.strip()
)

# 앱 접속(로그인/토큰 갱신) 시 발급되는 쿠폰 설정
# 기본값은 기존 가입 웰컴 쿠폰/캠페인을 재사용하되,
# 운영에서 분리하고 싶으면 환경변수로 재정의한다.
APP_OPEN_COUPON_TYPE_CODE = os.getenv("APP_OPEN_COUPON_TYPE_CODE", "WELCOME_3000")
APP_OPEN_CAMPAIGN_CODE = os.getenv("APP_OPEN_CAMPAIGN_CODE", "SIGNUP_WELCOME")
# DAILY | WEEKLY
APP_OPEN_PERIOD = os.getenv("APP_OPEN_PERIOD", "DAILY").upper()
# 기존 전체 발급 (APP_OPEN_COUPON_TYPE_CODE / APP_OPEN_CAMPAIGN_CODE)
APP_OPEN_LEGACY_ENABLED = os.getenv("APP_OPEN_LEGACY_ENABLED", "1") in ("1", "true", "True")
# 월(술집X) 수(술집) 1장씩, 3일 만료. LEGACY와 병행 가능
APP_OPEN_MON_WED_ENABLED = os.getenv("APP_OPEN_MON_WED_ENABLED", "0") in ("1", "true", "True")
# 데이트 기획전 앱접속 발급 (DATE_EVENT_SPECIAL + DATE_EVENT_APP_OPEN)
DATE_EVENT_APP_OPEN_ENABLED = os.getenv("DATE_EVENT_APP_OPEN_ENABLED", "1") in ("1", "true", "True")
DATE_EVENT_APP_OPEN_COUPON_TYPE_CODE = os.getenv(
    "DATE_EVENT_APP_OPEN_COUPON_TYPE_CODE",
    "DATE_EVENT_SPECIAL",
)
DATE_EVENT_APP_OPEN_CAMPAIGN_CODE = os.getenv(
    "DATE_EVENT_APP_OPEN_CAMPAIGN_CODE",
    "DATE_EVENT_APP_OPEN",
)
# 중간고사 기획전 앱접속 발급 (MIDTERM_EVENT_SPECIAL + MIDTERM_EVENT_APP_OPEN)
MIDTERM_EVENT_APP_OPEN_ENABLED = os.getenv("MIDTERM_EVENT_APP_OPEN_ENABLED", "0") in (
    "1",
    "true",
    "True",
)
MIDTERM_EVENT_APP_OPEN_COUPON_TYPE_CODE = os.getenv(
    "MIDTERM_EVENT_APP_OPEN_COUPON_TYPE_CODE",
    "MIDTERM_EVENT_SPECIAL",
)
MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE = os.getenv(
    "MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE",
    "MIDTERM_EVENT_APP_OPEN",
)
# 지정된 쿠폰 타입 코드들에 한해, 앱접속 발급 시 식당당 benefit 1개만 발급
APP_OPEN_SINGLE_BENEFIT_PER_RESTAURANT_CODES = {
    code.strip()
    for code in os.getenv(
        "APP_OPEN_SINGLE_BENEFIT_PER_RESTAURANT_CODES",
        "",
    ).split(",")
    if code.strip()
}
# 지정된 앱접속 쿠폰 타입 코드들에 한해 고정 만료시각 적용
APP_OPEN_FIXED_EXPIRY_COUPON_CODES = {
    code.strip()
    for code in os.getenv(
        "APP_OPEN_FIXED_EXPIRY_COUPON_CODES",
        "",
    ).split(",")
    if code.strip()
}


def _parse_app_open_fixed_expires_at():
    raw = (os.getenv("APP_OPEN_FIXED_EXPIRES_AT", "") or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except Exception:
        logger.warning(
            "Invalid APP_OPEN_FIXED_EXPIRES_AT value: %s (expected ISO datetime)",
            raw,
        )
        return None


APP_OPEN_FIXED_EXPIRES_AT = _parse_app_open_fixed_expires_at()


def _is_event_admin_user(user: User) -> bool:
    """운영진 계정인지 확인"""
    return user.kakao_id is not None and user.kakao_id in EVENT_ADMIN_KAKAO_IDS


def _build_app_open_issue_key(user: User) -> str:
    """
    앱 접속(로그인/토큰 갱신) 쿠폰의 멱등성을 보장하기 위한 issue_key 생성.
    - DAILY: APP_OPEN:<user_id>:YYYYMMDD
    - WEEKLY: APP_OPEN:<user_id>:YYYY-WW (ISO 주차 기준)
    """
    now = timezone.now()
    if APP_OPEN_PERIOD == "WEEKLY":
        year, week, _ = now.isocalendar()
        return f"APP_OPEN:{user.id}:{year:04d}-W{week:02d}"
    # 기본은 일 단위
    return f"APP_OPEN:{user.id}:{now:%Y%m%d}"


def _resolve_coupon_expiry_for_issue(
    coupon_type: CouponType,
    *,
    issued_at: datetime | None = None,
) -> datetime:
    """
    쿠폰 타입/이벤트 정책에 따라 발급 만료일을 결정.
    - APP_OPEN 고정 만료 쿠폰 타입이면 APP_OPEN_FIXED_EXPIRES_AT 우선 사용
    - 그 외는 기존 _expires_at 규칙 사용
    """
    # 데이트 기획전 쿠폰은 운영 정책상 이벤트 종료일(4/12)로 고정 만료
    if coupon_type.code == DATE_EVENT_APP_OPEN_COUPON_TYPE_CODE:
        return DATE_EVENT_COUPON_EXPIRES_AT

    # 중간고사 기획전 쿠폰은 운영 정책상 이벤트 종료일(4/24)로 고정 만료
    if coupon_type.code == "MIDTERM_EVENT_SPECIAL":
        return MIDTERM_EVENT_COUPON_EXPIRES_AT

    if (
        coupon_type.code in APP_OPEN_FIXED_EXPIRY_COUPON_CODES
        and APP_OPEN_FIXED_EXPIRES_AT is not None
    ):
        return APP_OPEN_FIXED_EXPIRES_AT
    return _expires_at(coupon_type, issued_at=issued_at)


def delete_expired_coupons_for_user(
    user: User,
    *,
    db_alias: str | None = None,
) -> int:
    """
    사용자 기준으로 만료된 쿠폰(ISSUED/EXPIRED)을 자동 삭제.
    반환값은 삭제된 Coupon row 수.
    """
    alias = db_alias or router.db_for_write(Coupon)
    now = timezone.now()
    expired_qs = Coupon.objects.using(alias).filter(
        user=user,
        status__in=["ISSUED", "EXPIRED"],
        expires_at__lt=now,
    )
    deleted, _ = expired_qs.delete()
    return deleted


MAX_COUPONS_PER_RESTAURANT = 200

# 기본(코드 하드코딩) 제외 식당 설정
# 30: 고니식탁, 147: 포차1번지먹새통, 65: 팀스 쿠치나 (쿠폰 발급 제외, 제휴는 유지)
# 148(Better), 284(와비사비)는 제휴 아님 → AffiliateRestaurant에 없음
# RESTAURANTS_EXCLUDED_FROM_ALL: 모든 쿠폰 발급에서 제외 (팀스 쿠치나 등)
RESTAURANTS_EXCLUDED_FROM_ALL: set[int] = {65}
# RESTAURANTS_EXCLUDED_FROM_NON_STAMP: 스탬프 적립 보상 쿠폰 제외, 그 외 모든 쿠폰 발급에서 제외 (고니식탁 등)
RESTAURANTS_EXCLUDED_FROM_NON_STAMP: set[int] = {30}
COUPON_TYPE_EXCLUDED_RESTAURANTS: dict[str, set[int]] = {
    "WELCOME_3000": {30, 65, 147},
    "REFERRAL_BONUS_REFERRER": {30, 65, 147},
    "REFERRAL_BONUS_REFEREE": {30, 65, 147},
    "FINAL_EXAM_SPECIAL": {30, 65},  # 고니식탁, 팀스 쿠치나 제외
    "NEW_SEMESTER_SPECIAL": {30, 65, 147},
    "KNULIKE": {30, 65, 147},
    # 학생회 한정 쿠폰: CSV 기준 쿠폰 미제공 식당(고니식탁, 포차1번지, 온새미로) 제외
    "DATELIKE": {30, 65, 147, 250},
    "FULL_AFFILIATE_SPECIAL": set(),  # RESTAURANTS_EXCLUDED_FROM_ALL(65)만 적용, 21종 전체 발급
    "APP_OPEN_MON": set(),  # 월요일 앱접속: 술집 아닌 식당, RESTAURANTS_EXCLUDED_FROM_ALL(65)만 적용
    "APP_OPEN_WED": set(),  # 수요일 앱접속: 술집, RESTAURANTS_EXCLUDED_FROM_ALL(65)만 적용
}

# 제휴식당 21종 전체 발급 쿠폰 코드 (코드 내에서 수정 가능)
FULL_AFFILIATE_COUPON_CODE = "DONGARILIKE"

# 부스 방문 추천코드 (전체 제휴식당 중 1개 쿠폰 발급)
BOOTH_VISIT_REF_CODE = "80THANNIVERSARY"
BOOTH_VISIT_SUBTITLE = "[🎁 부스 방문 쿠폰 🎁]"

# 룰렛 이벤트 추천코드 (제휴 매장 쿠폰 랜덤 N개 발급)
ROULETTE_SUBTITLE = "[🎰 룰렛 이벤트 쿠폰 🎰]"
ROULETTE_CODES: dict[str, int] = {
    "MINYEOL": 1,
    "EUNJIN": 5,
    "JAEMIN": 10,
    "CHAERIN": 30,
}

# (삭제됨) 미디움레어(고기굽기) 쿠폰 코드는 캠페인 종료로 제거
def _is_pub_restaurant(restaurant_id: int, *, db_alias: str | None = None) -> bool:
    """
    제휴 식당이 술집인지 판별.
    pub_option='네' 또는 '네,'로 시작, 또는 category='술집' 이면 True.
    """
    alias = db_alias or router.db_for_read(AffiliateRestaurant)
    try:
        r = (
            AffiliateRestaurant.objects.using(alias)
            .filter(restaurant_id=restaurant_id)
            .values("pub_option", "category")
            .first()
        )
    except DatabaseError:
        return False
    if not r:
        return False
    pub = (r.get("pub_option") or "").strip()
    cat = (r.get("category") or "").strip()
    return pub == "네" or pub.startswith("네,") or cat == "술집"


def _get_pub_restaurant_ids(
    restaurant_ids: list[int], *, db_alias: str | None = None
) -> list[int]:
    """restaurant_ids 중 술집만 반환."""
    return [rid for rid in restaurant_ids if _is_pub_restaurant(rid, db_alias=db_alias)]


def _get_non_pub_restaurant_ids(
    restaurant_ids: list[int], *, db_alias: str | None = None
) -> list[int]:
    """restaurant_ids 중 술집 아닌 식당만 반환."""
    return [rid for rid in restaurant_ids if not _is_pub_restaurant(rid, db_alias=db_alias)]


def _get_excluded_restaurant_ids(
    coupon_type_code: str,
    *,
    db_alias: str | None = None,
) -> set[int]:
    """
    쿠폰 타입별로 제외할 restaurant_id 집합을 반환.
    - RESTAURANTS_EXCLUDED_FROM_ALL (모든 쿠폰에서 제외)
    - RESTAURANTS_EXCLUDED_FROM_NON_STAMP (스탬프 보상 제외, 그 외 모든 쿠폰에서 제외)
    - 하드코딩된 COUPON_TYPE_EXCLUDED_RESTAURANTS
    - DB 기반 CouponRestaurantExclusion
    둘을 합집합으로 사용한다.
    """
    base = set(COUPON_TYPE_EXCLUDED_RESTAURANTS.get(coupon_type_code, set()))
    base |= RESTAURANTS_EXCLUDED_FROM_ALL
    # 스탬프 적립 보상 쿠폰이 아닌 경우, RESTAURANTS_EXCLUDED_FROM_NON_STAMP(고니식탁 등) 적용
    if not coupon_type_code.startswith("STAMP_REWARD"):
        base |= RESTAURANTS_EXCLUDED_FROM_NON_STAMP
    alias = db_alias or router.db_for_read(CouponRestaurantExclusion)
    extra = set(
        CouponRestaurantExclusion.objects.using(alias)
        .filter(coupon_type__code=coupon_type_code)
        .values_list("restaurant_id", flat=True)
    )
    return base | extra


def _get_valid_restaurant_ids_for_coupon_type(
    coupon_type: CouponType,
    *,
    db_alias: str | None = None,
) -> set[int]:
    """
    쿠폰 발급 대상 식당 ID 집합을 반환.
    - is_affiliate=True (제휴 식당)
    - RestaurantCouponBenefit 존재 (active=True)
    - 제외 목록 아님
    위 조건을 모두 만족하는 식당만 반환.
    """
    alias = db_alias or router.db_for_read(AffiliateRestaurant)
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    affiliate_ids = set(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    benefit_ids = set(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=coupon_type, active=True)
        .values_list("restaurant_id", flat=True)
        .distinct()
    )
    excluded_ids = _get_excluded_restaurant_ids(coupon_type.code, db_alias=alias)

    return (affiliate_ids & benefit_ids) - excluded_ids


def _build_benefit_snapshot(
    coupon_type: CouponType,
    restaurant_id: int,
    *,
    benefit: "RestaurantCouponBenefit | None" = None,
    db_alias: str | None = None,
    issue_type_label: str | None = None,
) -> dict:
    snapshot = {
        "coupon_type_code": coupon_type.code,
        "coupon_type_title": coupon_type.title,
        "restaurant_id": restaurant_id,
        "benefit": coupon_type.benefit_json,
        "title": coupon_type.title,
        "subtitle": "",
        "notes": "",
    }

    if benefit is None:
        benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)
        benefit = (
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(
                coupon_type=coupon_type,
                restaurant_id=restaurant_id,
                active=True,
            )
            .order_by("sort_order")
            .first()
        )

    if benefit:
        snapshot.update(
            {
                "title": benefit.title,
                "subtitle": benefit.subtitle,
                "benefit": benefit.benefit_json or coupon_type.benefit_json,
                "notes": benefit.notes or "",
                # coupon_type_title은 항상 CouponType의 title을 사용 (식당별 쿠폰 내용과 무관하게)
                "coupon_type_title": coupon_type.title,
            }
        )
        try:
            restaurant_name = getattr(benefit.restaurant, "name", None)
        except DatabaseError:
            restaurant_name = None
        if restaurant_name:
            snapshot["restaurant_name"] = restaurant_name
        if issue_type_label:
            snapshot["issue_type_label"] = issue_type_label
        return snapshot

    if issue_type_label:
        snapshot["issue_type_label"] = issue_type_label
    restaurant_alias = db_alias or router.db_for_read(AffiliateRestaurant)
    try:
        restaurant_name = (
            AffiliateRestaurant.objects.using(restaurant_alias)
            .filter(restaurant_id=restaurant_id)
            .values_list("name", flat=True)
            .first()
        )
    except DatabaseError:
        restaurant_name = None
    if restaurant_name:
        snapshot["restaurant_name"] = restaurant_name
    return snapshot


def _select_restaurant_for_coupon(ct: CouponType, *, db_alias: str | None = None) -> int:
    """
    쿠폰 발급 대상 식당 중 균등 분배로 한 식당을 선정.
    _get_valid_restaurant_ids_for_coupon_type(제휴+benefit+비제외) 기준으로만 선정.
    """
    alias = db_alias or router.db_for_write(Coupon)
    restaurant_ids = list(
        _get_valid_restaurant_ids_for_coupon_type(ct, db_alias=alias)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)

    counts = {}
    qs = (
        Coupon.objects.using(alias)
        .filter(coupon_type=ct)
        .exclude(restaurant_id__isnull=True)
        .values("restaurant_id")
        .annotate(cnt=Count("id"))
    )
    for row in qs:
        rid = row["restaurant_id"]
        if rid is None:
            continue
        counts[rid] = row["cnt"]

    random.shuffle(restaurant_ids)
    min_count = None
    candidates: list[int] = []
    for rid in restaurant_ids:
        if rid in excluded_ids:
            continue
        assigned = counts.get(rid, 0)
        if assigned >= MAX_COUPONS_PER_RESTAURANT:
            continue
        if min_count is None or assigned < min_count:
            min_count = assigned
            candidates = [rid]
        elif assigned == min_count:
            candidates.append(rid)

    if not candidates:
        raise ValidationError("coupon issuance limit reached for all restaurants")

    return random.choice(candidates)


def _select_single_restaurant_from_pool(
    ct: CouponType,
    pool_restaurant_ids: list[int],
    *,
    db_alias: str | None = None,
) -> int | None:
    """
    pool_restaurant_ids 중 benefit이 있고 제외되지 않은 식당 1개를 균등 분배로 선정.
    선정 불가 시 None 반환.
    """
    if not pool_restaurant_ids:
        return None
    alias = db_alias or router.db_for_write(Coupon)
    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    # benefit이 있는 식당만
    valid_ids = []
    for rid in pool_restaurant_ids:
        if rid in excluded_ids:
            continue
        has_benefit = (
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, restaurant_id=rid, active=True)
            .exists()
        )
        if has_benefit:
            valid_ids.append(rid)

    if not valid_ids:
        return None

    counts = {}
    qs = (
        Coupon.objects.using(alias)
        .filter(coupon_type=ct)
        .exclude(restaurant_id__isnull=True)
        .values("restaurant_id")
        .annotate(cnt=Count("id"))
    )
    for row in qs:
        rid = row["restaurant_id"]
        if rid is not None:
            counts[rid] = row["cnt"]

    random.shuffle(valid_ids)
    min_count = None
    candidates: list[int] = []
    for rid in valid_ids:
        assigned = counts.get(rid, 0)
        if assigned >= MAX_COUPONS_PER_RESTAURANT:
            continue
        if min_count is None or assigned < min_count:
            min_count = assigned
            candidates = [rid]
        elif assigned == min_count:
            candidates.append(rid)

    return random.choice(candidates) if candidates else None


def _create_coupon_with_restaurant(
    *,
    user: User,
    coupon_type: CouponType,
    campaign: Campaign | None,
    issue_key: str | None,
    db_alias: str | None = None,
    code: str | None = None,
    expires_at: datetime | None = None,
    extra_fields: dict | None = None,
) -> Coupon:
    alias = db_alias or router.db_for_write(Coupon)
    fields = {
        "code": code or make_coupon_code(),
        "user": user,
        "coupon_type": coupon_type,
        "campaign": campaign,
        "expires_at": expires_at or _expires_at(coupon_type),
        "issue_key": issue_key,
    }
    if extra_fields:
        fields.update(extra_fields)

    lock_key = f"lock:coupon:assign:{coupon_type.id}"
    with redis_lock(lock_key, ttl=5):
        restaurant_id = _select_restaurant_for_coupon(coupon_type, db_alias=alias)
        fields["restaurant_id"] = restaurant_id
        if "benefit_snapshot" not in fields:
            fields["benefit_snapshot"] = _build_benefit_snapshot(
                coupon_type, restaurant_id, db_alias=alias
            )
        return Coupon.objects.using(alias).create(**fields)

def _expires_at(ct: CouponType, *, issued_at: datetime | None = None) -> datetime:
    """
    CouponType.valid_days > 0 이면 발급일 + valid_days 일의 23:59:59 반환.
    발급 시각의 timezone을 유지 (예: KST 발급 → KST 23:59:59 만료).
    그 외에는 GLOBAL_COUPON_EXPIRY 반환.

    만료일 표시 예시 (valid_days=3, 발급 월요일 10:00 KST):
    - expires_at: 2026-03-19T23:59:59+09:00 (목요일 23:59 KST)
    - API: "2026-03-19T14:59:59.000000Z" (UTC)
    - 프론트엔드: "~3/19(목) 23:59까지" 또는 "3일 후 만료"
    """
    # 스탬프 보상 쿠폰은 운영 정책상 항상 글로벌 만료일로 고정
    if (ct.code or "").startswith("STAMP_REWARD"):
        return GLOBAL_COUPON_EXPIRY

    if ct.valid_days and ct.valid_days > 0:
        base = issued_at or timezone.now()
        if timezone.is_naive(base):
            base = timezone.make_aware(base)
        expiry_date = (base + timedelta(days=ct.valid_days)).date()
        # 발급 시각과 동일한 tzinfo 사용 (KST 발급 → KST 만료)
        tz = base.tzinfo
        return datetime.combine(expiry_date, time(23, 59, 59), tzinfo=tz)
    return GLOBAL_COUPON_EXPIRY


def ensure_invite_code(user: User) -> InviteCode:
    # 일반 사용자는 campaign_code가 없는 기본 InviteCode 하나만 가짐
    invite = InviteCode.objects.filter(user=user, campaign_code__isnull=True).first()
    if invite:
        return invite

    max_attempts = 32
    for attempt in range(max_attempts):
        length = 12 if attempt >= 8 else 8
        code = make_coupon_code(length).upper()
        if InviteCode.objects.filter(code=code).exists():
            continue
        try:
            return InviteCode.objects.create(user=user, code=code, campaign_code=None)
        except IntegrityError:
            continue

    fallback_code = f"INV{user.id:06d}{uuid.uuid4().hex[:4].upper()}"
    invite, _ = InviteCode.objects.update_or_create(
        user=user,
        campaign_code__isnull=True,
        defaults={"code": fallback_code[:16]},
    )
    return invite



def _issue_coupons_for_target_restaurants(
    *,
    user: User,
    coupon_type: CouponType,
    campaign: Campaign,
    issue_key_prefix: str,
    db_alias: str | None = None,
) -> list:
    """
    앱접속/엠버서더/기획전과 동일하게 17개 식당 전체에 대해 benefit 수만큼 쿠폰 발급.
    """
    alias = db_alias or router.db_for_write(Coupon)
    all_restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    excluded_ids = _get_excluded_restaurant_ids(coupon_type.code, db_alias=alias)
    target_restaurant_ids = [rid for rid in all_restaurant_ids if rid not in excluded_ids]

    issued: list = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    for restaurant_id in target_restaurant_ids:
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=coupon_type, restaurant_id=restaurant_id, active=True)
            .order_by("sort_order")
        )
        if not benefits:
            continue

        for sort_order, benefit in enumerate(benefits):
            issue_key = f"{issue_key_prefix}:{restaurant_id}:{sort_order}"
            existing = (
                Coupon.objects.using(alias)
                .filter(
                    user=user,
                    coupon_type=coupon_type,
                    campaign=campaign,
                    issue_key=issue_key,
                    restaurant_id=restaurant_id,
                )
                .first()
            )
            if existing:
                issued.append(existing)
                continue

            try:
                benefit_snapshot = _build_benefit_snapshot(
                    coupon_type, restaurant_id, benefit=benefit, db_alias=alias
                )
                coupon = Coupon.objects.using(alias).create(
                    code=make_coupon_code(),
                    user=user,
                    coupon_type=coupon_type,
                    campaign=campaign,
                    restaurant_id=restaurant_id,
                    expires_at=_expires_at(coupon_type),
                    issue_key=issue_key,
                    benefit_snapshot=benefit_snapshot,
                )
                issued.append(coupon)
            except IntegrityError:
                dup = (
                    Coupon.objects.using(alias)
                    .filter(
                        user=user,
                        coupon_type=coupon_type,
                        campaign=campaign,
                        issue_key=issue_key,
                        restaurant_id=restaurant_id,
                    )
                    .first()
                )
                if dup:
                    issued.append(dup)
    return issued


def _issue_coupons_for_single_restaurant(
    *,
    user: User,
    coupon_type: CouponType,
    campaign: Campaign,
    issue_key_prefix: str,
    db_alias: str | None = None,
    issue_type_label: str | None = None,
) -> list:
    """
    한 식당만 선정하여 해당 식당에 대해 쿠폰을 발급한다.
    - 신규가입(WELCOME_3000), 친구초대 추천인(REFERRAL_BONUS_REFERRER): 식당당 benefit 첫 행 1장.
    - 친구초대 피추천인(REFERRAL_BONUS_REFEREE): 해당 식당에 활성 benefit이 여러 줄이면
      그중 무작위 1줄만 골라 1장 발급(한 번의 보상에 4종이 동시에 나가지 않음).
    """
    alias = db_alias or router.db_for_write(Coupon)
    restaurant_id = _select_restaurant_for_coupon(coupon_type, db_alias=alias)

    issued: list = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)
    benefit_qs = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=coupon_type, restaurant_id=restaurant_id, active=True)
        .order_by("sort_order", "id")
    )
    if coupon_type.code == "REFERRAL_BONUS_REFEREE":
        pool = list(benefit_qs)
        if not pool:
            return issued
        benefits = [random.choice(pool)]
    else:
        benefits = list(benefit_qs[:1])
    if not benefits:
        return issued

    for benefit in benefits:
        sort_key = getattr(benefit, "sort_order", 0)
        issue_key = f"{issue_key_prefix}:{restaurant_id}:{sort_key}"
        existing = (
            Coupon.objects.using(alias)
            .filter(
                user=user,
                coupon_type=coupon_type,
                campaign=campaign,
                issue_key=issue_key,
                restaurant_id=restaurant_id,
            )
            .first()
        )
        if existing:
            issued.append(existing)
            continue

        try:
            benefit_snapshot = _build_benefit_snapshot(
                coupon_type,
                restaurant_id,
                benefit=benefit,
                db_alias=alias,
                issue_type_label=issue_type_label,
            )
            coupon = Coupon.objects.using(alias).create(
                code=make_coupon_code(),
                user=user,
                coupon_type=coupon_type,
                campaign=campaign,
                restaurant_id=restaurant_id,
                expires_at=_expires_at(coupon_type),
                issue_key=issue_key,
                benefit_snapshot=benefit_snapshot,
            )
            issued.append(coupon)
        except IntegrityError:
            dup = (
                Coupon.objects.using(alias)
                .filter(
                    user=user,
                    coupon_type=coupon_type,
                    campaign=campaign,
                    issue_key=issue_key,
                    restaurant_id=restaurant_id,
                )
                .first()
            )
            if dup:
                issued.append(dup)
    return issued


def issue_signup_coupon(user: User):
    """신규가입 시 한 식당의 쿠폰만 발급."""
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="WELCOME_3000")
    camp = Campaign.objects.using(alias).get(code="SIGNUP_WELCOME", active=True)
    return _issue_coupons_for_single_restaurant(
        user=user,
        coupon_type=ct,
        campaign=camp,
        issue_key_prefix=f"SIGNUP:{user.id}",
        db_alias=alias,
        issue_type_label="신규가입 쿠폰",
    )


def _issue_app_open_mon_wed(user: User, *, db_alias: str | None = None):
    """
    APP_OPEN_MODE=MON_WED 일 때: 월(술집X 1장), 수(술집 1장)만 발급.
    한국 시간 기준 요일 체크. valid_days=3 적용.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

    alias = db_alias or router.db_for_write(Coupon)
    kst = timezone.now().astimezone(ZoneInfo("Asia/Seoul"))
    weekday = kst.weekday()  # 0=Mon, 2=Wed

    if weekday == 0:
        ct_code, camp_code = "APP_OPEN_MON", "APP_OPEN_MON_EVENT"
        is_pub_filter = False  # 술집 아닌 식당
    elif weekday == 2:
        ct_code, camp_code = "APP_OPEN_WED", "APP_OPEN_WED_EVENT"
        is_pub_filter = True  # 술집
    else:
        return []

    try:
        ct = CouponType.objects.using(alias).get(code=ct_code)
        camp = Campaign.objects.using(alias).get(code=camp_code, active=True)
    except (CouponType.DoesNotExist, Campaign.DoesNotExist):
        logger.warning(
            "app-open mon/wed: CouponType %s or Campaign %s not found",
            ct_code,
            camp_code,
        )
        return []

    date_str = kst.strftime("%Y%m%d")
    issue_key = f"{ct_code}:{user.id}:{date_str}"

    existing = (
        Coupon.objects.using(alias)
        .filter(user=user, coupon_type=ct, campaign=camp, issue_key=issue_key)
        .first()
    )
    if existing:
        return [existing]

    all_restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if is_pub_filter:
        pool_ids = _get_pub_restaurant_ids(all_restaurant_ids, db_alias=alias)
    else:
        pool_ids = _get_non_pub_restaurant_ids(all_restaurant_ids, db_alias=alias)

    restaurant_id = _select_single_restaurant_from_pool(ct, pool_ids, db_alias=alias)
    if not restaurant_id:
        logger.warning(
            "app-open mon/wed: no eligible restaurant (ct=%s, is_pub=%s)",
            ct_code,
            is_pub_filter,
        )
        return []

    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)
    benefit = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
        .order_by("sort_order")
        .first()
    )
    if not benefit:
        return []

    benefit_snapshot = _build_benefit_snapshot(
        ct, restaurant_id, benefit=benefit, db_alias=alias
    )
    # 한국 시간 기준 만료일 계산 (3일 후 23:59 KST)
    try:
        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_expires_at(ct, issued_at=kst),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        return [coupon]
    except IntegrityError:
        dup = (
            Coupon.objects.using(alias)
            .filter(user=user, coupon_type=ct, campaign=camp, issue_key=issue_key)
            .first()
        )
        return [dup] if dup else []


def _issue_app_open_legacy(user: User, *, db_alias: str | None = None) -> list:
    """
    기존 앱 접속 쿠폰 로직: 전체 제휴식당 benefit 수만큼 발급.
    APP_OPEN_COUPON_TYPE_CODE / APP_OPEN_CAMPAIGN_CODE 사용.
    """
    alias = db_alias or router.db_for_write(Coupon)

    try:
        ct = CouponType.objects.using(alias).get(code=APP_OPEN_COUPON_TYPE_CODE)
        camp = Campaign.objects.using(alias).get(
            code=APP_OPEN_CAMPAIGN_CODE, active=True
        )
    except CouponType.DoesNotExist:
        logger.warning(
            "app-open coupon not issued: CouponType %s does not exist",
            APP_OPEN_COUPON_TYPE_CODE,
        )
        return []
    except Campaign.DoesNotExist:
        logger.warning(
            "app-open coupon not issued: Campaign %s does not exist or inactive",
            APP_OPEN_CAMPAIGN_CODE,
        )
        return []

    now = timezone.now()
    if camp.start_at and now < camp.start_at:
        logger.info(
            "app-open campaign not started yet "
            "(campaign_code=%s, user=%s, now=%s, start_at=%s)",
            camp.code,
            user.id,
            now,
            camp.start_at,
        )
        return []
    if camp.end_at and now > camp.end_at:
        logger.info(
            "app-open campaign already ended "
            "(campaign_code=%s, user=%s, now=%s, end_at=%s)",
            camp.code,
            user.id,
            now,
            camp.end_at,
        )
        return []

    base_issue_key = _build_app_open_issue_key(user)

    all_restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not all_restaurant_ids:
        logger.warning(
            "app-open coupon not issued: no affiliate restaurants found "
            "(coupon_type=%s, campaign=%s, user=%s)",
            ct.code,
            camp.code,
            user.id,
        )
        return []

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    target_restaurant_ids = [rid for rid in all_restaurant_ids if rid not in excluded_ids]

    if not target_restaurant_ids:
        logger.warning(
            "app-open coupon not issued: no eligible restaurants after exclusions "
            "(coupon_type=%s, campaign=%s, user=%s)",
            ct.code,
            camp.code,
            user.id,
        )
        return []

    issued: list[Coupon] = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    # 배치: 식당별 benefit + 당일 발급분 쿠폰을 한 번에 조회 (쿠폰함 진입 시 N*2 쿼리 폭증 방지)
    benefits_qs = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(
            coupon_type=ct,
            restaurant_id__in=target_restaurant_ids,
            active=True,
        )
        .order_by("restaurant_id", "sort_order")
    )
    benefits_by_rid: dict[int, list] = defaultdict(list)
    for b in benefits_qs:
        benefits_by_rid[b.restaurant_id].append(b)

    existing_by_key = {
        c.issue_key: c
        for c in Coupon.objects.using(alias).filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key__startswith=base_issue_key + ":",
        )
    }

    for restaurant_id in target_restaurant_ids:
        benefits = benefits_by_rid.get(restaurant_id, [])
        if ct.code in APP_OPEN_SINGLE_BENEFIT_PER_RESTAURANT_CODES:
            benefits = benefits[:1]
        if not benefits:
            continue

        for sort_order, benefit in enumerate(benefits):
            issue_key = f"{base_issue_key}:{restaurant_id}:{sort_order}"

            existing = existing_by_key.get(issue_key)
            if existing:
                issued.append(existing)
                continue

            try:
                benefit_snapshot = _build_benefit_snapshot(
                    ct,
                    restaurant_id,
                    benefit=benefit,
                    db_alias=alias,
                )
                coupon = Coupon.objects.using(alias).create(
                    code=make_coupon_code(),
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    restaurant_id=restaurant_id,
                    expires_at=_resolve_coupon_expiry_for_issue(ct),
                    issue_key=issue_key,
                    benefit_snapshot=benefit_snapshot,
                )
                issued.append(coupon)
                existing_by_key[issue_key] = coupon
            except IntegrityError:
                dup = (
                    Coupon.objects.using(alias)
                    .filter(
                        user=user,
                        coupon_type=ct,
                        campaign=camp,
                        issue_key=issue_key,
                        restaurant_id=restaurant_id,
                    )
                    .first()
                )
                if dup:
                    issued.append(dup)
                    existing_by_key[issue_key] = dup

    return issued


def _issue_date_event_app_open(user: User, *, db_alias: str | None = None) -> list:
    """
    데이트 기획전 앱접속 쿠폰 발급.
    - DATE_EVENT_SPECIAL 타입의 식당별 benefit을 사용자에게 전체 발급
    - campaign(start_at/end_at, active) 범위 내에서만 발급
    - 이벤트 기간 동안 사용자당 식당별 1회 발급
    """
    alias = db_alias or router.db_for_write(Coupon)
    try:
        ct = CouponType.objects.using(alias).get(code=DATE_EVENT_APP_OPEN_COUPON_TYPE_CODE)
        camp = Campaign.objects.using(alias).get(
            code=DATE_EVENT_APP_OPEN_CAMPAIGN_CODE,
            active=True,
        )
    except CouponType.DoesNotExist:
        logger.info(
            "date-event app-open not issued: coupon type missing (code=%s)",
            DATE_EVENT_APP_OPEN_COUPON_TYPE_CODE,
        )
        return []
    except Campaign.DoesNotExist:
        logger.info(
            "date-event app-open not issued: campaign missing/inactive (code=%s)",
            DATE_EVENT_APP_OPEN_CAMPAIGN_CODE,
        )
        return []

    now = timezone.now()
    if camp.start_at and now < camp.start_at:
        return []
    if camp.end_at and now > camp.end_at:
        return []

    all_restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not all_restaurant_ids:
        return []

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    target_restaurant_ids = [rid for rid in all_restaurant_ids if rid not in excluded_ids]
    if not target_restaurant_ids:
        return []

    issued: list[Coupon] = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    key_prefix = f"DATE_EVENT_APP_OPEN:{user.id}:"
    benefits_qs = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(
            coupon_type=ct,
            restaurant_id__in=target_restaurant_ids,
            active=True,
        )
        .order_by("restaurant_id", "sort_order")
    )
    benefits_by_rid: dict[int, list] = defaultdict(list)
    for b in benefits_qs:
        benefits_by_rid[b.restaurant_id].append(b)

    existing_keys = set(
        Coupon.objects.using(alias)
        .filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key__startswith=key_prefix,
        )
        .values_list("issue_key", flat=True)
    )

    for restaurant_id in target_restaurant_ids:
        benefits = benefits_by_rid.get(restaurant_id, [])
        if not benefits:
            continue

        for sort_order, benefit in enumerate(benefits):
            issue_key = f"DATE_EVENT_APP_OPEN:{user.id}:{restaurant_id}:{sort_order}"
            if issue_key in existing_keys:
                continue

            benefit_snapshot = _build_benefit_snapshot(
                ct,
                restaurant_id,
                benefit=benefit,
                db_alias=alias,
            )
            if benefit_snapshot:
                benefit_snapshot = {
                    **benefit_snapshot,
                    "coupon_type_title": "[중간고사 캠페인 📚]",
                    "subtitle": "[중간고사 캠페인 📚]",
                }
            try:
                coupon = Coupon.objects.using(alias).create(
                    code=make_coupon_code(),
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    restaurant_id=restaurant_id,
                    expires_at=_resolve_coupon_expiry_for_issue(ct),
                    issue_key=issue_key,
                    benefit_snapshot=benefit_snapshot,
                )
                issued.append(coupon)
                existing_keys.add(issue_key)
            except IntegrityError:
                dup = (
                    Coupon.objects.using(alias)
                    .filter(
                        user=user,
                        coupon_type=ct,
                        campaign=camp,
                        issue_key=issue_key,
                        restaurant_id=restaurant_id,
                    )
                    .first()
                )
                if dup:
                    issued.append(dup)
                    existing_keys.add(issue_key)

    return issued


def _issue_midterm_event_app_open(user: User, *, db_alias: str | None = None) -> list:
    """
    중간고사 기획전 앱접속 쿠폰 발급.
    - MIDTERM_EVENT_SPECIAL 타입의 식당별 benefit을 사용자에게 전체 발급
    - campaign(start_at/end_at, active) 범위 내에서만 발급
    - 이벤트 기간 동안 사용자당 식당별 1회 발급
    """
    alias = db_alias or router.db_for_write(Coupon)
    try:
        ct = CouponType.objects.using(alias).get(code=MIDTERM_EVENT_APP_OPEN_COUPON_TYPE_CODE)
        camp = Campaign.objects.using(alias).get(
            code=MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE,
            active=True,
        )
    except CouponType.DoesNotExist:
        logger.info(
            "midterm-event app-open not issued: coupon type missing (code=%s)",
            MIDTERM_EVENT_APP_OPEN_COUPON_TYPE_CODE,
        )
        return []
    except Campaign.DoesNotExist:
        logger.info(
            "midterm-event app-open not issued: campaign missing/inactive (code=%s)",
            MIDTERM_EVENT_APP_OPEN_CAMPAIGN_CODE,
        )
        return []

    now = timezone.now()
    if camp.start_at and now < camp.start_at:
        return []
    if camp.end_at and now > camp.end_at:
        return []

    all_restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not all_restaurant_ids:
        return []

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    target_restaurant_ids = [rid for rid in all_restaurant_ids if rid not in excluded_ids]
    if not target_restaurant_ids:
        return []

    issued: list[Coupon] = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)

    key_prefix = f"MIDTERM_EVENT_APP_OPEN:{user.id}:"
    benefits_qs = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(
            coupon_type=ct,
            restaurant_id__in=target_restaurant_ids,
            active=True,
        )
        .order_by("restaurant_id", "sort_order")
    )
    benefits_by_rid: dict[int, list] = defaultdict(list)
    for b in benefits_qs:
        benefits_by_rid[b.restaurant_id].append(b)

    existing_keys = set(
        Coupon.objects.using(alias)
        .filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key__startswith=key_prefix,
        )
        .values_list("issue_key", flat=True)
    )

    for restaurant_id in target_restaurant_ids:
        benefits = benefits_by_rid.get(restaurant_id, [])
        if not benefits:
            continue

        for sort_order, benefit in enumerate(benefits):
            issue_key = f"MIDTERM_EVENT_APP_OPEN:{user.id}:{restaurant_id}:{sort_order}"
            if issue_key in existing_keys:
                continue

            benefit_snapshot = _build_benefit_snapshot(
                ct,
                restaurant_id,
                benefit=benefit,
                db_alias=alias,
            )
            try:
                coupon = Coupon.objects.using(alias).create(
                    code=make_coupon_code(),
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    restaurant_id=restaurant_id,
                    expires_at=_resolve_coupon_expiry_for_issue(ct),
                    issue_key=issue_key,
                    benefit_snapshot=benefit_snapshot,
                )
                issued.append(coupon)
                existing_keys.add(issue_key)
            except IntegrityError:
                dup = (
                    Coupon.objects.using(alias)
                    .filter(
                        user=user,
                        coupon_type=ct,
                        campaign=camp,
                        issue_key=issue_key,
                        restaurant_id=restaurant_id,
                    )
                    .first()
                )
                if dup:
                    issued.append(dup)
                    existing_keys.add(issue_key)

    return issued


def issue_app_open_coupon(user: User):
    """
    앱 접속(로그인/토큰 갱신 등) 시점에 발급되는 쿠폰.
    APP_OPEN_LEGACY_ENABLED / APP_OPEN_MON_WED_ENABLED / DATE_EVENT_APP_OPEN_ENABLED / MIDTERM_EVENT_APP_OPEN_ENABLED
    로 각각 온오프 가능.
    """
    issued: list[Coupon] = []
    alias = router.db_for_write(Coupon)

    if DATE_EVENT_APP_OPEN_ENABLED:
        issued.extend(_issue_date_event_app_open(user, db_alias=alias))

    if MIDTERM_EVENT_APP_OPEN_ENABLED:
        issued.extend(_issue_midterm_event_app_open(user, db_alias=alias))

    if APP_OPEN_LEGACY_ENABLED:
        issued.extend(_issue_app_open_legacy(user, db_alias=alias))

    if APP_OPEN_MON_WED_ENABLED:
        issued.extend(_issue_app_open_mon_wed(user, db_alias=alias))

    return issued


@transaction.atomic
def issue_ambassador_coupons(
    user: User,
    *,
    campaign_code: str | None = None,
    coupon_type_code: str | None = None,
):
    """
    엠버서더/일괄 전송을 위해 특정 사용자에게 전체 제휴식당 쿠폰을 발급합니다.
    신규가입 쿠폰과 동일한 쿠폰 타입(WELCOME_3000)을 기본 사용하지만,
    각 식당마다 고유한 issue_key를 사용하여 중복 발급 방지 제약조건을 통과합니다.

    Args:
        user: 쿠폰을 발급받을 사용자
        campaign_code: 캠페인 코드 (기본: SIGNUP_WELCOME). 기획전 구분용.
        coupon_type_code: 쿠폰 타입 코드 (기본: WELCOME_3000).

    Returns:
        발급된 쿠폰 리스트
    """
    alias = router.db_for_write(Coupon)
    ct_code = coupon_type_code or "WELCOME_3000"
    camp_code = campaign_code or "SIGNUP_WELCOME"
    ct = CouponType.objects.using(alias).get(code=ct_code)
    camp = Campaign.objects.using(alias).get(code=camp_code, active=True)
    
    # 전체 제휴식당 목록 가져오기 (is_affiliate=True)
    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")
    
    # 제외된 식당 필터링 (하드코딩 + DB 설정 반영)
    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    valid_restaurant_ids = [rid for rid in restaurant_ids if rid not in excluded_ids]
    
    if not valid_restaurant_ids:
        raise ValidationError("no valid restaurants available after exclusions")
    
    issued_coupons = []
    failed_restaurants = []
    
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)
    for restaurant_id in valid_restaurant_ids:
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
            .order_by("sort_order")
        )
        if not benefits:
            continue
        for sort_order, benefit in enumerate(benefits):
            try:
                issue_key = f"AMBASSADOR:{user.id}:{restaurant_id}:{sort_order}"
                existing = Coupon.objects.using(alias).filter(
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    issue_key=issue_key,
                ).first()
                if existing:
                    issued_coupons.append(existing)
                    continue
                benefit_snapshot = _build_benefit_snapshot(
                    ct, restaurant_id, benefit=benefit, db_alias=alias
                )
                benefit_snapshot["subtitle"] = "엠버서더 특별 쿠폰"
                coupon = Coupon.objects.using(alias).create(
                    code=make_coupon_code(),
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    restaurant_id=restaurant_id,
                    expires_at=_expires_at(ct),
                    issue_key=issue_key,
                    benefit_snapshot=benefit_snapshot,
                )
                issued_coupons.append(coupon)
            except Exception as exc:
                logger.error(
                    f"Failed to issue ambassador coupon - "
                    f"user={user.id}, restaurant={restaurant_id}, error={str(exc)}",
                    exc_info=True,
                )
                failed_restaurants.append((restaurant_id, str(exc)))
    
    if failed_restaurants:
        logger.warning(
            f"Some coupons failed to issue - "
            f"user={user.id}, failed_count={len(failed_restaurants)}, "
            f"failed_restaurants={failed_restaurants}"
        )
    
    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "failed_restaurants": failed_restaurants,
    }


def _issue_event_reward_coupons(
    *,
    user: User,
    campaign_code: str,
    coupon_type_code: str,
    code_used: str,
    db_alias: str | None = None,
) -> list:
    """
    기획전 추천코드 입력 시 피추천인에게 전체 제휴식당(18개) 쿠폰을 발급합니다.
    일반 친구초대와 달리 1개가 아닌 전체 식당에 대해 각 1개씩 발급합니다.
    """
    alias = db_alias or router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code=coupon_type_code)
    camp = Campaign.objects.using(alias).get(code=campaign_code, active=True)

    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    valid_restaurant_ids = [rid for rid in restaurant_ids if rid not in excluded_ids]
    if not valid_restaurant_ids:
        raise ValidationError("no valid restaurants available after exclusions")

    issued: list = []
    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)
    for restaurant_id in valid_restaurant_ids:
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
            .order_by("sort_order")
        )
        if not benefits:
            continue
        for sort_order, benefit in enumerate(benefits):
            issue_key = f"EVENT_REWARD:{user.id}:{code_used}:{restaurant_id}:{sort_order}"
            existing = (
                Coupon.objects.using(alias)
                .filter(
                    user=user,
                    coupon_type=ct,
                    campaign=camp,
                    issue_key=issue_key,
                )
                .first()
            )
            if existing:
                issued.append(existing)
                continue
            benefit_snapshot = _build_benefit_snapshot(
                ct, restaurant_id, benefit=benefit, db_alias=alias
            )
            coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_expires_at(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued.append(coupon)
    return issued


@transaction.atomic
def issue_final_exam_coupons(user: User):
    """
    기말고사 특별 이벤트 쿠폰을 사용자에게 전체 제휴식당 쿠폰을 발급합니다.
    한 사람당 하나의 쿠폰 세트만 받을 수 있도록 issue_key로 제어합니다.
    
    Args:
        user: 쿠폰을 발급받을 사용자
        
    Returns:
        발급된 쿠폰 리스트
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
    camp = Campaign.objects.using(alias).get(code="FINAL_EXAM_EVENT", active=True)
    
    # 이미 발급된 쿠폰이 있는지 확인 (한 사람당 하나의 쿠폰 세트만)
    existing_coupons = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
    )
    
    if existing_coupons.exists():
        # 이미 발급된 쿠폰이 있으면 기존 쿠폰 반환
        return {
            "coupons": list(existing_coupons),
            "total_issued": existing_coupons.count(),
            "failed_restaurants": [],
            "already_issued": True,
        }
    
    # 전체 제휴식당 목록 가져오기 (is_affiliate=True)
    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")
    
    # 제외된 식당 필터링 (하드코딩 + DB 설정 반영)
    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    valid_restaurant_ids = [rid for rid in restaurant_ids if rid not in excluded_ids]
    
    if not valid_restaurant_ids:
        raise ValidationError("no valid restaurants available after exclusions")
    
    issued_coupons = []
    failed_restaurants = []
    
    # 사용자당 하나의 쿠폰 세트만 발급되도록 동일한 issue_key 사용
    base_issue_key = f"FINAL_EXAM:{user.id}"
    
    for restaurant_id in valid_restaurant_ids:
        try:
            # 각 식당마다 고유한 issue_key 사용 (식당 ID 포함)
            issue_key = f"{base_issue_key}:{restaurant_id}"
            
            # 이미 발급된 쿠폰이 있는지 확인 (중복 발급 방지)
            existing = Coupon.objects.using(alias).filter(
                user=user,
                coupon_type=ct,
                campaign=camp,
                issue_key=issue_key,
            ).first()
            
            if existing:
                logger.info(
                    f"Coupon already exists for final exam event - "
                    f"user={user.id}, restaurant={restaurant_id}, coupon_code={existing.code}"
                )
                issued_coupons.append(existing)
                continue
            
            # 쿠폰 생성
            benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, db_alias=alias)
            coupon = Coupon.objects.using(alias).create(
                code=make_coupon_code(),
                user=user,
                coupon_type=ct,
                campaign=camp,
                restaurant_id=restaurant_id,
                expires_at=_expires_at(ct),
                issue_key=issue_key,
                benefit_snapshot=benefit_snapshot,
            )
            issued_coupons.append(coupon)
            logger.info(
                f"Final exam coupon issued - "
                f"user={user.id}, restaurant={restaurant_id}, coupon_code={coupon.code}"
            )
        except Exception as exc:
            logger.error(
                f"Failed to issue final exam coupon - "
                f"user={user.id}, restaurant={restaurant_id}, error={str(exc)}",
                exc_info=True
            )
            failed_restaurants.append((restaurant_id, str(exc)))
    
    if failed_restaurants:
        logger.warning(
            f"Some coupons failed to issue - "
            f"user={user.id}, failed_count={len(failed_restaurants)}, "
            f"failed_restaurants={failed_restaurants}"
        )
    
    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "failed_restaurants": failed_restaurants,
        "already_issued": False,
    }


@transaction.atomic
def issue_full_affiliate_coupons(user: User):
    """
    제휴식당 21종 전체 쿠폰을 사용자에게 발급합니다.
    FULL_AFFILIATE_COUPON_CODE 입력 시 사용됩니다.
    한 사람당 하나의 쿠폰 세트만 받을 수 있습니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
    camp = Campaign.objects.using(alias).get(code="FULL_AFFILIATE_EVENT", active=True)

    existing_coupons = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
    )
    if existing_coupons.exists():
        return {
            "coupons": list(existing_coupons),
            "total_issued": existing_coupons.count(),
            "failed_restaurants": [],
            "already_issued": True,
        }

    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias)
        .filter(is_affiliate=True)
        .values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    valid_restaurant_ids = [rid for rid in restaurant_ids if rid not in excluded_ids]
    if not valid_restaurant_ids:
        raise ValidationError("no valid restaurants available after exclusions")

    issued_coupons = []
    failed_restaurants = []
    base_issue_key = f"FULL_AFFILIATE:{user.id}"

    for restaurant_id in valid_restaurant_ids:
        try:
            issue_key = f"{base_issue_key}:{restaurant_id}"
            existing = Coupon.objects.using(alias).filter(
                user=user,
                coupon_type=ct,
                campaign=camp,
                issue_key=issue_key,
            ).first()
            if existing:
                issued_coupons.append(existing)
                continue

            benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, db_alias=alias)
            coupon = Coupon.objects.using(alias).create(
                code=make_coupon_code(),
                user=user,
                coupon_type=ct,
                campaign=camp,
                restaurant_id=restaurant_id,
                expires_at=_expires_at(ct),
                issue_key=issue_key,
                benefit_snapshot=benefit_snapshot,
            )
            issued_coupons.append(coupon)
        except Exception as exc:
            logger.error(
                f"Failed to issue full affiliate coupon - "
                f"user={user.id}, restaurant={restaurant_id}, error={str(exc)}",
                exc_info=True,
            )
            failed_restaurants.append((restaurant_id, str(exc)))

    if failed_restaurants:
        logger.warning(
            f"Some full affiliate coupons failed - "
            f"user={user.id}, failed_count={len(failed_restaurants)}, "
            f"failed_restaurants={failed_restaurants}"
        )

    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "failed_restaurants": failed_restaurants,
        "already_issued": False,
    }


@transaction.atomic
def issue_booth_visit_coupon(user: User, *, ref_code_used: str = BOOTH_VISIT_REF_CODE):
    """
    부스 방문 추천코드(80THANNIVERSARY) 입력 시 전체 제휴식당 중 1개 쿠폰을 발급합니다.
    - FULL_AFFILIATE_SPECIAL의 식당별 benefit 풀을 재사용합니다.
    - 사용자당 한 번만 발급됩니다.
    - subtitle은 항상 [🎁 부스 방문 쿠폰 🎁] 로 고정합니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
    camp = Campaign.objects.using(alias).get(code="BOOTH_VISIT_EVENT", active=True)

    existing = Coupon.objects.using(alias).filter(user=user, coupon_type=ct, campaign=camp)
    if existing.exists():
        return {"coupons": list(existing), "total_issued": existing.count(), "already_issued": True}

    restaurant_id = _select_restaurant_for_coupon(ct, db_alias=alias)
    issue_key = f"EVENT_REWARD:{user.id}:{ref_code_used}:{restaurant_id}:0"
    guard = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
        issue_key=issue_key,
    ).first()
    if guard:
        return {"coupons": [guard], "total_issued": 1, "already_issued": True}

    benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, db_alias=alias)
    if benefit_snapshot:
        benefit_snapshot = {**benefit_snapshot, "subtitle": BOOTH_VISIT_SUBTITLE}

    coupon = Coupon.objects.using(alias).create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        restaurant_id=restaurant_id,
        expires_at=_expires_at(ct),
        issue_key=issue_key,
        benefit_snapshot=benefit_snapshot,
    )
    return {"coupons": [coupon], "total_issued": 1, "already_issued": False}


@transaction.atomic
def issue_roulette_coupons(
    user: User,
    *,
    campaign_code: str,
    ref_code_used: str,
    count: int,
    subtitle: str = ROULETTE_SUBTITLE,
):
    """
    룰렛 이벤트 추천코드 입력 시 제휴 매장 쿠폰을 랜덤으로 N개 발급합니다.
    - FULL_AFFILIATE_SPECIAL의 식당별 benefit 풀을 재사용합니다.
    - 사용자당 해당 campaign_code 기준 1회만 발급됩니다.
    - subtitle은 항상 고정값으로 덮어씁니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
    camp = Campaign.objects.using(alias).get(code=campaign_code, active=True)

    existing = Coupon.objects.using(alias).filter(user=user, coupon_type=ct, campaign=camp)
    if existing.exists():
        return {"coupons": list(existing), "total_issued": existing.count(), "already_issued": True}

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)
    benefits = list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, active=True)
        .exclude(restaurant_id__in=excluded_ids)
        .order_by("restaurant_id", "sort_order")
    )
    if not benefits:
        raise ValidationError("no benefits available for roulette coupon assignment")

    sample_size = min(int(count), len(benefits))
    selected_benefits = random.sample(benefits, sample_size)

    issued_coupons: list[Coupon] = []
    base_issue_key = f"EVENT_REWARD:{user.id}:{ref_code_used}"
    for benefit in selected_benefits:
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{base_issue_key}:{restaurant_id}:{sort_order}"

        guard = Coupon.objects.using(alias).filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key=issue_key,
        ).first()
        if guard:
            issued_coupons.append(guard)
            continue

        benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit, db_alias=alias)
        if benefit_snapshot:
            benefit_snapshot = {
                **benefit_snapshot,
                "coupon_type_title": subtitle,
                "subtitle": subtitle,
            }

        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_expires_at(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued_coupons.append(coupon)

    return {"coupons": issued_coupons, "total_issued": len(issued_coupons), "already_issued": False}


NEW_SEMESTER_COUPON_COUNT = 3


@transaction.atomic
def issue_new_semester_coupons(user: User):
    """
    신학기 추천코드(newsemeseter) 입력 시 사용자에게 제휴식당 쿠폰 3개를 발급합니다.
    전체 쿠폰 풀(제휴식당 16개 × 식당별 benefit) 중 3개를 랜덤 선정하여 발급합니다.
    사용자당 한 번만 발급됩니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="NEW_SEMESTER_SPECIAL")
    camp = Campaign.objects.using(alias).get(code="NEW_SEMESTER_EVENT", active=True)

    existing_coupons = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
    )
    if existing_coupons.exists():
        return {
            "coupons": list(existing_coupons),
            "total_issued": existing_coupons.count(),
            "already_issued": True,
        }

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)

    benefits = list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, active=True)
        .exclude(restaurant_id__in=excluded_ids)
        .order_by("restaurant_id", "sort_order")
    )
    if not benefits:
        raise ValidationError("no benefits available for new semester coupon assignment")

    sample_size = min(NEW_SEMESTER_COUPON_COUNT, len(benefits))
    selected_benefits = random.sample(benefits, sample_size)

    issued_coupons = []
    base_issue_key = f"NEW_SEMESTER:{user.id}"
    for idx, benefit in enumerate(selected_benefits):
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{base_issue_key}:{restaurant_id}:{sort_order}"

        existing = Coupon.objects.using(alias).filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key=issue_key,
        ).first()
        if existing:
            issued_coupons.append(existing)
            continue

        benefit_snapshot = _build_benefit_snapshot(
            ct, restaurant_id, benefit=benefit, db_alias=alias
        )
        # newsemester 쿠폰 상세정보: [개강 응원 쿠폰 💪]
        if benefit_snapshot:
            benefit_snapshot = {
                **benefit_snapshot,
                "coupon_type_title": "[개강 응원 쿠폰 💪]",
                "subtitle": "[개강 응원 쿠폰 💪]",
            }
        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_expires_at(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued_coupons.append(coupon)

    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "already_issued": False,
    }


KNULIKE_COUPON_COUNT = 3


@transaction.atomic
def issue_knulike_coupons(user: User):
    """
    KNULIKE 추천코드 입력 시 사용자에게 제휴식당 쿠폰 3개를 발급합니다.
    개강 기념 쿠폰(NEW_SEMESTER_SPECIAL)과 동일한 조건입니다.
    전체 쿠폰 풀(제휴식당 16개 × 식당별 benefit) 중 3개를 랜덤 선정하여 발급합니다.
    사용자당 한 번만 발급됩니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="KNULIKE")
    camp = Campaign.objects.using(alias).get(code="KNULIKE_EVENT", active=True)

    existing_coupons = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
    )
    if existing_coupons.exists():
        return {
            "coupons": list(existing_coupons),
            "total_issued": existing_coupons.count(),
            "already_issued": True,
        }

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)

    benefits = list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, active=True)
        .exclude(restaurant_id__in=excluded_ids)
        .order_by("restaurant_id", "sort_order")
    )
    if not benefits:
        raise ValidationError("no benefits available for knulike coupon assignment")

    sample_size = min(KNULIKE_COUPON_COUNT, len(benefits))
    selected_benefits = random.sample(benefits, sample_size)

    issued_coupons = []
    base_issue_key = f"KNULIKE:{user.id}"
    for idx, benefit in enumerate(selected_benefits):
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{base_issue_key}:{restaurant_id}:{sort_order}"

        existing = Coupon.objects.using(alias).filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key=issue_key,
        ).first()
        if existing:
            issued_coupons.append(existing)
            continue

        benefit_snapshot = _build_benefit_snapshot(
            ct, restaurant_id, benefit=benefit, db_alias=alias
        )
        if benefit_snapshot:
            benefit_snapshot = {
                **benefit_snapshot,
                "coupon_type_title": "[학생회 제휴 쿠폰 🤝]",
                "subtitle": "[학생회 제휴 쿠폰 🤝]",
            }
        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_expires_at(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued_coupons.append(coupon)

    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "already_issued": False,
    }


DATELIKE_COUPON_COUNT = 3


@transaction.atomic
def issue_datelike_coupons(user: User):
    """
    DATELIKE 추천코드 입력 시 사용자에게 제휴식당 쿠폰 3개를 발급합니다.
    전체 제휴식당 중 DATELIKE benefit이 있는 식당 풀에서 3개를 랜덤 선정합니다.
    사용자당 한 번만 발급됩니다.
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="DATELIKE")
    camp = Campaign.objects.using(alias).get(code="DATELIKE_EVENT", active=True)

    existing_coupons = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
    )
    if existing_coupons.exists():
        return {
            "coupons": list(existing_coupons),
            "total_issued": existing_coupons.count(),
            "already_issued": True,
        }

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)

    benefits = list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, active=True)
        .exclude(restaurant_id__in=excluded_ids)
        .order_by("restaurant_id", "sort_order")
    )
    if not benefits:
        raise ValidationError("no benefits available for datelike coupon assignment")

    sample_size = min(DATELIKE_COUPON_COUNT, len(benefits))
    selected_benefits = random.sample(benefits, sample_size)

    issued_coupons = []
    base_issue_key = f"DATELIKE:{user.id}"
    for benefit in selected_benefits:
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{base_issue_key}:{restaurant_id}:{sort_order}"

        existing = Coupon.objects.using(alias).filter(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key=issue_key,
        ).first()
        if existing:
            issued_coupons.append(existing)
            continue

        benefit_snapshot = _build_benefit_snapshot(
            ct, restaurant_id, benefit=benefit, db_alias=alias
        )
        if benefit_snapshot:
            benefit_snapshot = {
                **benefit_snapshot,
                "coupon_type_title": "[학생회 한정 쿠폰 💕]",
                "subtitle": "[학생회 한정 쿠폰 💕]",
            }
        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_resolve_coupon_expiry_for_issue(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued_coupons.append(coupon)

    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "already_issued": False,
    }


@transaction.atomic
def claim_final_exam_coupon(user: User, coupon_code: str):
    """
    쿠폰 코드를 입력받아 기말고사 특별 이벤트 쿠폰을 발급합니다.
    
    Args:
        user: 쿠폰을 발급받을 사용자
        coupon_code: 입력받은 쿠폰 코드 (WOULDULIKEEX)
        
    Returns:
        발급된 쿠폰 정보
    """
    # 쿠폰 코드 검증
    if coupon_code.upper() != "WOULDULIKEEX":
        raise ValidationError("invalid coupon code")
    
    # 쿠폰 발급
    result = issue_final_exam_coupons(user)
    
    if result["already_issued"]:
        raise ValidationError("이미 발급받은 쿠폰입니다. 한 사람당 하나의 쿠폰 세트만 받을 수 있습니다.")
    
    return result


MIDTERM_STUDYLIKE_COUPON_CODE = "STUDYLIKE"
MIDTERM_STUDYLIKE_COUPON_COUNT = 3
MIDTERM_STUDYLIKE_CAMPAIGN_CODE = "MIDTERM_EVENT_STUDYLIKE"

# 중간고사 캠페인: 날짜별 쿠폰코드 / 25분 챌린지 코드
MIDTERM_DAILY_CAMPAIGN_CODE = "MIDTERM_EVENT_DAILY_CODES"
MIDTERM_DAILY_CODE_START_AT = datetime(2026, 4, 14, 15, 0, 0, tzinfo=timezone.utc)  # 4/15 00:00 KST
MIDTERM_DAILY_SUBTITLE = "[중간고사 캠페인 📚]"

# 코드(대문자) → {"store": 매장명, "coupon": 쿠폰 설명} (CSV 기준) — 사람이 수정하지 않도록 JSON 원문으로 로드
MIDTERM_DAILY_CODE_META: dict[str, dict] = json.loads(
    "{\"BDTLKDG\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"BJLWVCF\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"BJQWNIG\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"BJWQNJG\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"BKTPQLE\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"BLTVQMF\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"BMXTQEG\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"BPRNWFH\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"BQVMXAG\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"BQXKDHI\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"BTVJPGI\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"BVKRNKE\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"CDJMRKC\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"CJDRQMC\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"CKLQRGB\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"CKMRWBE\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"CKQWNEE\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"CPJMRDC\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"CQXJRIC\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"CRDVQFC\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"CRWJTHC\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"CVDRPJC\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"CVQJPLC\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"DJVTRGF\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"DKTRNHE\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"DKVCPMJ\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"DKXQLFI\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"DLVJQEC\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"DNVPRLJ\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"DPRNJBG\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"DWNXLII\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"FVQTMAD\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"GVDJMCC\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"HCNWKAE\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"HJCNKHG\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"HJWMXFD\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"HMXPTDE\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"HNRXWLD\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"HPMKWID\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"HPTMXED\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"HQLMTJD\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"HQRPLGD\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"HQTPWKD\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"HVKLMCH\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"HWMKTMD\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"HWMKYBH\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"JTNWCBC\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"JWKQNDI\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"KCPTRKI\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"KPLNWAB\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"LMDRKJH\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"LNVKPHB\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"LQPVSBD\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"LQWMRFA\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"LWQVKDD\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"LXPMWGG\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"LZTNVBK\": {\"coupon\": \"(캠페인 쿠폰) 랜덤 1종\", \"store\": \"25분 챌린지용\"}, \"MCTXQLI\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"MKWQPIA\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"MNBXTCJ\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"MTCVPFJ\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"MTRQVAA\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"MXVLQKJ\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"NKXWPJE\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"NLBTKFE\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"NQKJVAI\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"NQXPRME\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"NTDRQIE\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"NWQXRCB\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"NWXKQGE\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"NXLVQKB\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"NXRKPEB\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"PLDQKLH\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"PLKTRCA\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"PMTRXDJ\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"PMXQLHD\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"PTQRMJA\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"QCLVTEI\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"QCRNKGH\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"QCVTMIJ\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"QMVLTBA\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"QNRCWDF\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"QTPRNCG\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"QTRNPLA\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"QTRXLMI\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"QWXJCPD\": {\"coupon\": \"(캠페인 쿠폰) 랜덤 1종\", \"store\": \"25분 챌린지용\"}, \"QXPTNJI\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"QXRPCFF\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"RCKWNMG\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"RCLVTBI\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"RDMTCKG\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"RJLPTAF\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"RJVLPEF\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"RJWNTLG\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"RKMVYEF\": {\"coupon\": \"(캠페인 쿠폰) 랜덤 1종\", \"store\": \"25분 챌린지용\"}, \"RPXWTGA\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"RTNXLDB\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"RTPVCJF\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"RVTLNIB\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"TKRPMIH\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"TLDRWAH\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"TQWPMEA\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"TRMPLCD\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"TRMVPHH\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"TRWQPKA\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"VDCLMJJ\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"VKQPWDA\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"VQWLPHF\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"VTMKDFG\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"VTMNDGC\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"VTQKRMA\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"VTXQLBF\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"WCPRXAJ\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"WPDNKEH\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}, \"WQJNVKH\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"XCKQNCE\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"XCVPRDH\": {\"coupon\": \"생연어덮밥 10,000원 식사권\", \"store\": \"마름모식당\"}, \"XDMWKLB\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"XLVCPIF\": {\"coupon\": \"[17~20시 사용]\\n9,000원 이상 결제시 (테이블 당)\\n모든 유부 2P 제공\", \"store\": \"정직유부 경북대점\"}, \"XNWLKJB\": {\"coupon\": \"아메리카노 / 라떼 / 아이스티\\n사이즈 업\", \"store\": \"웃찌커피\"}, \"XPLNWMB\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"XPTKNFB\": {\"coupon\": \"뻥튀기 아이스크림 제공\", \"store\": \"사랑과평화 경북대점\"}, \"XQTRPHA\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"XRDKPBB\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"YHMPQRA\": {\"coupon\": \"(캠페인 쿠폰) 랜덤 1종\", \"store\": \"25분 챌린지용\"}, \"YMKQRGJ\": {\"coupon\": \"감자튀김 제공\", \"store\": \"부리또익스프레스\"}, \"YNPLTHJ\": {\"coupon\": \"인당 해시포테이토 1개\", \"store\": \"고씨네 대구경북대본점\"}, \"YPLXQKF\": {\"coupon\": \"갈릭버터 프라이즈 변경\\n(버거 주문시)\", \"store\": \"기프트버거 경대점\"}, \"YPMDJMH\": {\"coupon\": \"인원수 맞게 새우튀김 서비스\", \"store\": \"혜화문식당\"}, \"YRDQPCI\": {\"coupon\": \"샐러드 구매시)\\n- 아메리카노 기본사이즈 1,000원\\n- 아메리카노 빅사이즈 1,000원\", \"store\": \"스톡홀롬샐러드 경대정문점\"}, \"YVMCQLF\": {\"coupon\": \"고기 추가\\n(방문시 - 소고기류 제외)\", \"store\": \"다원국밥\"}, \"ZDXRJAC\": {\"coupon\": \"추억의 도시락\", \"store\": \"통통주먹구이 경북대점\"}, \"ZQNXPBJ\": {\"coupon\": \"미니빙수 제공\", \"store\": \"포차1번지먹새통 경북대점\"}, \"ZTRPJEJ\": {\"coupon\": \"우유 푸딩 테이크아웃 시\\n아메리카노 500원\", \"store\": \"주비 두루 향기롭다\"}}"
)

# 25분 챌린지용: 코드 → 랜덤 발급 개수 (CSV 기준)
MIDTERM_CHALLENGE_CODE_COUNTS: dict[str, int] = json.loads(
    "{\"BTLQWGH\": 3, \"CPNXJIK\": 3, \"DFLPRWX\": 10, \"DVRYMLN\": 3, \"RVKJXTA\": 5, \"SWMNPUB\": 5}"
)


def _normalize_text(value: str) -> str:
    return "".join((value or "").strip().split())


def _resolve_midterm_restaurant_id_from_store_name(store_name: str) -> int | None:
    """
    매장명(브랜치 포함 가능)으로 AffiliateRestaurant.restaurant_id를 최대한 안정적으로 찾는다.
    - RestaurantCouponBenefit에서 restaurant_id를 찾기 위한 용도
    - 로컬/테스트에서 restaurants 테이블이 없으면 None 반환
    """
    alias = router.db_for_read(AffiliateRestaurant)
    raw = (store_name or "").strip()
    if not raw:
        return None

    # 지점명 제거를 위해 첫 토큰(브랜드명에 가까운 부분)을 우선 사용
    base = raw.split()[0]
    candidates = [raw, base]

    try:
        for q in candidates:
            q = q.strip()
            if not q:
                continue
            rid = (
                AffiliateRestaurant.objects.using(alias)
                .filter(name__icontains=q)
                .values_list("restaurant_id", flat=True)
                .first()
            )
            if rid:
                return int(rid)
    except DatabaseError:
        return None

    return None


@transaction.atomic
def claim_midterm_daily_code_coupon(user: User, coupon_code: str):
    """
    중간고사 캠페인 날짜별/챌린지용 쿠폰 코드 입력 시 발급.
    - 기간: 4/15 00:00 KST ~ 4/24 23:59:59 KST
    - 제한(A): 코드 1개당 사용자 1회 (동일 코드 재입력 중복 발급 불가)
    - 일반 코드: 해당 매장 쿠폰 1장 발급
    - 챌린지 코드: MIDTERM_EVENT_SPECIAL 풀에서 랜덤 N장 발급
    """
    code = (coupon_code or "").strip().upper()
    if not code:
        raise ValidationError("invalid coupon code")

    now = timezone.now()
    if now < MIDTERM_DAILY_CODE_START_AT:
        raise ValidationError("expired")
    if now > MIDTERM_EVENT_COUPON_EXPIRES_AT:
        raise ValidationError("expired")

    alias = router.db_for_write(Coupon)
    try:
        ct = CouponType.objects.using(alias).get(code="MIDTERM_EVENT_SPECIAL")
        camp = Campaign.objects.using(alias).get(code=MIDTERM_DAILY_CAMPAIGN_CODE, active=True)
    except (CouponType.DoesNotExist, Campaign.DoesNotExist):
        raise ValidationError("event not configured")

    # 멱등성(코드 1회성): 같은 코드는 같은 issue_key로 막음
    issue_key_prefix = f"MIDTERM_DAILY:{user.id}:{code}"
    existing_qs = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
        issue_key__startswith=issue_key_prefix,
    )
    if existing_qs.exists():
        return {
            "coupons": list(existing_qs.order_by("issued_at", "id")),
            "total_issued": existing_qs.count(),
            "already_issued": True,
        }

    # 챌린지 코드: 랜덤 N종
    if code in MIDTERM_CHALLENGE_CODE_COUNTS:
        count = int(MIDTERM_CHALLENGE_CODE_COUNTS[code])
        excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
        benefit_alias = router.db_for_read(RestaurantCouponBenefit)
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, active=True)
            .exclude(restaurant_id__in=excluded_ids)
            .order_by("restaurant_id", "sort_order")
        )
        if not benefits:
            raise ValidationError("no benefits available for midterm daily code assignment")

        sample_size = min(count, len(benefits))
        selected_benefits = random.sample(benefits, sample_size)

        issued: list[Coupon] = []
        for benefit in selected_benefits:
            restaurant_id = benefit.restaurant_id
            sort_order = getattr(benefit, "sort_order", 0)
            issue_key = f"{issue_key_prefix}:{restaurant_id}:{sort_order}"

            benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit, db_alias=alias)
            if benefit_snapshot:
                benefit_snapshot = {
                    **benefit_snapshot,
                    "coupon_type_title": MIDTERM_DAILY_SUBTITLE,
                    "subtitle": MIDTERM_DAILY_SUBTITLE,
                }

            coupon = Coupon.objects.using(alias).create(
                code=make_coupon_code(),
                user=user,
                coupon_type=ct,
                campaign=camp,
                restaurant_id=restaurant_id,
                expires_at=_resolve_coupon_expiry_for_issue(ct),
                issue_key=issue_key,
                benefit_snapshot=benefit_snapshot,
            )
            issued.append(coupon)

        return {"coupons": issued, "total_issued": len(issued), "already_issued": False}

    # 일반 코드: 매장 1장
    meta = MIDTERM_DAILY_CODE_META.get(code)
    if not meta:
        raise ValidationError("invalid coupon code")

    store_name = (meta.get("store") or "").strip()
    if store_name in ("25분 챌린지용",):
        # 랜덤 1종 코드는 CHALLENGE_CODE_COUNTS에 포함되지 않으므로 여기서 처리
        count = 1
        excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
        benefit_alias = router.db_for_read(RestaurantCouponBenefit)
        benefits = list(
            RestaurantCouponBenefit.objects.using(benefit_alias)
            .filter(coupon_type=ct, active=True)
            .exclude(restaurant_id__in=excluded_ids)
            .order_by("restaurant_id", "sort_order")
        )
        if not benefits:
            raise ValidationError("no benefits available for midterm daily code assignment")
        benefit = random.choice(benefits)
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{issue_key_prefix}:{restaurant_id}:{sort_order}"
        benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit, db_alias=alias)
        if benefit_snapshot:
            benefit_snapshot = {**benefit_snapshot, "coupon_type_title": MIDTERM_DAILY_SUBTITLE, "subtitle": MIDTERM_DAILY_SUBTITLE}
        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_resolve_coupon_expiry_for_issue(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        return {"coupons": [coupon], "total_issued": 1, "already_issued": False}

    restaurant_id = _resolve_midterm_restaurant_id_from_store_name(store_name)
    if restaurant_id is None:
        raise ValidationError("invalid coupon code")

    benefit_alias = router.db_for_read(RestaurantCouponBenefit)
    benefit = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, restaurant_id=restaurant_id, active=True)
        .order_by("sort_order")
        .first()
    )
    if not benefit:
        raise ValidationError("invalid coupon code")

    issue_key = issue_key_prefix
    benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit, db_alias=alias)
    if benefit_snapshot:
        benefit_snapshot = {
            **benefit_snapshot,
            "coupon_type_title": MIDTERM_DAILY_SUBTITLE,
            "subtitle": MIDTERM_DAILY_SUBTITLE,
        }
    coupon = Coupon.objects.using(alias).create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        restaurant_id=restaurant_id,
        expires_at=_resolve_coupon_expiry_for_issue(ct),
        issue_key=issue_key,
        benefit_snapshot=benefit_snapshot,
    )
    return {"coupons": [coupon], "total_issued": 1, "already_issued": False}


@transaction.atomic
def claim_midterm_studylike_coupon(user: User, coupon_code: str):
    """
    쿠폰 코드를 입력받아 중간고사 기획전 쿠폰을 랜덤 발급합니다.
    - 코드: STUDYLIKE (대소문자 무관)
    - 기간: 현재~2026-04-24 23:59:59 KST (쿠폰 만료도 동일하게 고정)
    - 구성: MIDTERM_EVENT_SPECIAL benefit 풀(13종) 중 3종 무작위 발급 (중복 없음)
    - 사용자당 1회만 발급
    """
    if (coupon_code or "").strip().upper() != MIDTERM_STUDYLIKE_COUPON_CODE:
        raise ValidationError("invalid coupon code")

    now = timezone.now()
    if now > MIDTERM_EVENT_COUPON_EXPIRES_AT:
        raise ValidationError("expired")

    alias = router.db_for_write(Coupon)
    try:
        ct = CouponType.objects.using(alias).get(code="MIDTERM_EVENT_SPECIAL")
        camp = Campaign.objects.using(alias).get(
            code=MIDTERM_STUDYLIKE_CAMPAIGN_CODE, active=True
        )
    except (CouponType.DoesNotExist, Campaign.DoesNotExist):
        # 운영/스테이징에서 마이그레이션 누락 또는 캠페인 비활성화 시
        raise ValidationError("event not configured")

    issue_key_prefix = f"MIDTERM_STUDYLIKE:{user.id}:"
    existing_qs = Coupon.objects.using(alias).filter(
        user=user,
        coupon_type=ct,
        campaign=camp,
        issue_key__startswith=issue_key_prefix,
    )
    if existing_qs.exists():
        return {
            "coupons": list(existing_qs.order_by("issued_at", "id")),
            "total_issued": existing_qs.count(),
            "already_issued": True,
        }

    excluded_ids = _get_excluded_restaurant_ids(ct.code, db_alias=alias)
    benefit_alias = router.db_for_read(RestaurantCouponBenefit)
    benefits = list(
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .filter(coupon_type=ct, active=True)
        .exclude(restaurant_id__in=excluded_ids)
        .order_by("restaurant_id", "sort_order")
    )
    if not benefits:
        raise ValidationError("event not configured")

    sample_size = min(MIDTERM_STUDYLIKE_COUPON_COUNT, len(benefits))
    selected_benefits = random.sample(benefits, sample_size)

    issued_coupons: list[Coupon] = []
    for benefit in selected_benefits:
        restaurant_id = benefit.restaurant_id
        sort_order = getattr(benefit, "sort_order", 0)
        issue_key = f"{issue_key_prefix}{restaurant_id}:{sort_order}"

        benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, benefit=benefit, db_alias=alias)
        if benefit_snapshot:
            benefit_snapshot = {
                **benefit_snapshot,
                "coupon_type_title": "[학생회 한정 쿠폰 📚]",
                "subtitle": "[학생회 한정 쿠폰 📚]",
            }

        coupon = Coupon.objects.using(alias).create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            restaurant_id=restaurant_id,
            expires_at=_resolve_coupon_expiry_for_issue(ct),
            issue_key=issue_key,
            benefit_snapshot=benefit_snapshot,
        )
        issued_coupons.append(coupon)

    return {
        "coupons": issued_coupons,
        "total_issued": len(issued_coupons),
        "already_issued": False,
    }


@transaction.atomic
def redeem_coupon(user: User, coupon_code: str, restaurant_id: int, pin: str):
    alias = router.db_for_write(Coupon)
    coupon = locked_get(Coupon.objects, using_alias=alias, code=coupon_code, user=user)
    if coupon.status != "ISSUED":
        raise ValidationError("already used or invalid state")

    now = timezone.now()
    if coupon.expires_at <= now:
        coupon.status = "EXPIRED"
        coupon.save(update_fields=["status"], using=alias)
        raise ValidationError("expired")

    if not _verify_pin(restaurant_id, pin):
        raise ValidationError("invalid merchant code")

    lock_key = f"lock:coupon:{coupon.id}"
    with redis_lock(lock_key, ttl=5):
        coupon.refresh_from_db(using=alias)
        if coupon.status != "ISSUED":
            raise ValidationError("already used")
        if coupon.expires_at <= timezone.now():
            coupon.status = "EXPIRED"
            coupon.save(update_fields=["status"], using=alias)
            raise ValidationError("expired")

        coupon.status = "REDEEMED"
        coupon.redeemed_at = timezone.now()
        coupon.restaurant_id = restaurant_id
        coupon.benefit_snapshot = _build_benefit_snapshot(
            coupon.coupon_type, restaurant_id, db_alias=alias
        )
        coupon.save(using=alias)
    return coupon



@transaction.atomic
def check_and_expire_coupon(user: User, coupon_code: str) -> dict:
    """Check coupon validity; if expired, mark EXPIRED and return status."""
    alias = router.db_for_write(Coupon)
    coupon = locked_get(Coupon.objects, using_alias=alias, code=coupon_code, user=user)

    now = timezone.now()
    if coupon.status == "ISSUED" and coupon.expires_at <= now:
        coupon.status = "EXPIRED"
        coupon.save(update_fields=["status"], using=alias)

    restaurant_id = coupon.restaurant_id
    benefit_snapshot = coupon.benefit_snapshot
    updated_snapshot = False

    if restaurant_id and not benefit_snapshot:
        benefit_snapshot = _build_benefit_snapshot(
            coupon.coupon_type,
            restaurant_id,
            db_alias=alias,
        )
        updated_snapshot = True

    if not benefit_snapshot:
        benefit_snapshot = {
            "coupon_type_code": coupon.coupon_type.code,
            "coupon_type_title": coupon.coupon_type.title,
            "restaurant_id": restaurant_id,
            "benefit": coupon.coupon_type.benefit_json,
            "title": coupon.coupon_type.title,
            "subtitle": "",
            "notes": "",
        }

    restaurant_name = benefit_snapshot.get("restaurant_name")
    if restaurant_name is None and restaurant_id:
        restaurant_alias = router.db_for_read(AffiliateRestaurant)
        try:
            restaurant_name = (
                AffiliateRestaurant.objects.using(restaurant_alias)
                .filter(restaurant_id=restaurant_id)
                .values_list("name", flat=True)
                .first()
            )
        except DatabaseError:
            restaurant_name = None
        if restaurant_name:
            benefit_snapshot["restaurant_name"] = restaurant_name
            updated_snapshot = True

    if updated_snapshot:
        Coupon.objects.using(alias).filter(pk=coupon.pk).update(
            benefit_snapshot=benefit_snapshot
        )

    return {
        "code": coupon.code,
        "status": coupon.status,
        "expires_at": coupon.expires_at,
        "redeemed_at": coupon.redeemed_at,
        "campaign": coupon.campaign_id,
        "coupon_type": coupon.coupon_type_id,
        "restaurant_id": coupon.restaurant_id,
        "restaurant_name": restaurant_name,
        "benefit": benefit_snapshot,
        "issue_key": coupon.issue_key,
    }



def accept_referral(*, referee: User, ref_code: str) -> Referral:

    db_alias = router.db_for_write(Referral)

    # 대소문자 구분 없이 조회 (앱 안내: "추천 코드는 대소문자를 구분하지 않아요")
    ref_code = (ref_code or "").strip().upper()

    # 차단된 쿠폰 코드 목록
    BLOCKED_CODES = {"01KBWVFS", "01KBWVFSSNEE"}
    
    if ref_code in BLOCKED_CODES:
        raise ValidationError("invalid referral code")
    
    # 신학기 추천코드 이벤트 처리 (newsemester / newsemeseter)
    if ref_code in ("NEWSEMESTER", "NEWSEMESETER"):
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="NEW_SEMESTER_SPECIAL")
        camp = Campaign.objects.using(alias).get(code="NEW_SEMESTER_EVENT", active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 신학기 추천코드 쿠폰을 발급받았습니다.",
                code="new_semester_already_issued",
            )

        result = issue_new_semester_coupons(referee)
        if result["already_issued"]:
            raise ValidationError(
                "이미 신학기 추천코드 쿠폰을 발급받았습니다.",
                code="new_semester_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="NEW_SEMESTER_EVENT",
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 신학기 추천코드 쿠폰을 발급받았습니다.",
                            code="new_semester_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="NEW_SEMESTER_EVENT",
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 신학기 추천코드 쿠폰을 발급받았습니다.",
                code="new_semester_already_issued",
            )

    # KNULIKE 추천코드 이벤트 처리 (개강 기념 쿠폰과 동일하게 3개 발급)
    if ref_code == "KNULIKE":
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="KNULIKE")
        camp = Campaign.objects.using(alias).get(code="KNULIKE_EVENT", active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 KNULIKE 추천코드 쿠폰을 발급받았습니다.",
                code="knulike_already_issued",
            )

        result = issue_knulike_coupons(referee)
        if result["already_issued"]:
            raise ValidationError(
                "이미 KNULIKE 추천코드 쿠폰을 발급받았습니다.",
                code="knulike_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="KNULIKE_EVENT",
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 KNULIKE 추천코드 쿠폰을 발급받았습니다.",
                            code="knulike_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="KNULIKE_EVENT",
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 KNULIKE 추천코드 쿠폰을 발급받았습니다.",
                code="knulike_already_issued",
            )

    # DATELIKE 추천코드 이벤트 처리 (학생회 한정 쿠폰 3개 발급)
    if ref_code == "DATELIKE":
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="DATELIKE")
        camp = Campaign.objects.using(alias).get(code="DATELIKE_EVENT", active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 DATELIKE 추천코드 쿠폰을 발급받았습니다.",
                code="datelike_already_issued",
            )

        result = issue_datelike_coupons(referee)
        if result["already_issued"]:
            raise ValidationError(
                "이미 DATELIKE 추천코드 쿠폰을 발급받았습니다.",
                code="datelike_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="DATELIKE_EVENT",
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 DATELIKE 추천코드 쿠폰을 발급받았습니다.",
                            code="datelike_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="DATELIKE_EVENT",
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 DATELIKE 추천코드 쿠폰을 발급받았습니다.",
                code="datelike_already_issued",
            )

    # 제휴식당 21종 전체 발급 쿠폰 코드 처리
    if ref_code == FULL_AFFILIATE_COUPON_CODE.upper():
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.using(alias).get(code="FULL_AFFILIATE_EVENT", active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 제휴식당 전체 쿠폰을 발급받았습니다.",
                code="full_affiliate_already_issued",
            )

        result = issue_full_affiliate_coupons(referee)
        if result["already_issued"]:
            raise ValidationError(
                "이미 제휴식당 전체 쿠폰을 발급받았습니다.",
                code="full_affiliate_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="FULL_AFFILIATE_EVENT",
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 제휴식당 전체 쿠폰을 발급받았습니다.",
                            code="full_affiliate_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="FULL_AFFILIATE_EVENT",
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 제휴식당 전체 쿠폰을 발급받았습니다.",
                code="full_affiliate_already_issued",
            )

    # 부스 방문 추천코드 이벤트 처리 (80THANNIVERSARY: 제휴식당 쿠폰 1개 발급)
    if ref_code == BOOTH_VISIT_REF_CODE.upper():
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.using(alias).get(code="BOOTH_VISIT_EVENT", active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 부스 방문 쿠폰을 발급받았습니다.",
                code="booth_visit_already_issued",
            )

        result = issue_booth_visit_coupon(referee, ref_code_used=ref_code)
        if result["already_issued"]:
            raise ValidationError(
                "이미 부스 방문 쿠폰을 발급받았습니다.",
                code="booth_visit_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="BOOTH_VISIT_EVENT",
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 부스 방문 쿠폰을 발급받았습니다.",
                            code="booth_visit_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="BOOTH_VISIT_EVENT",
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 부스 방문 쿠폰을 발급받았습니다.",
                code="booth_visit_already_issued",
            )

    # 룰렛 이벤트 추천코드 처리 (MINYEOL/EUNJIN/JAEMIN/CHAERIN)
    if ref_code in ROULETTE_CODES:
        issue_count = ROULETTE_CODES[ref_code]
        campaign_code = f"ROULETTE_{ref_code}_EVENT"

        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="FULL_AFFILIATE_SPECIAL")
        camp = Campaign.objects.using(alias).get(code=campaign_code, active=True)

        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        if existing_coupons.exists():
            raise ValidationError(
                "이미 룰렛 쿠폰을 발급받았습니다.",
                code="roulette_already_issued",
            )

        result = issue_roulette_coupons(
            referee,
            campaign_code=campaign_code,
            ref_code_used=ref_code,
            count=issue_count,
            subtitle=ROULETTE_SUBTITLE,
        )
        if result["already_issued"]:
            raise ValidationError(
                "이미 룰렛 쿠폰을 발급받았습니다.",
                code="roulette_already_issued",
            )

        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()

                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code=campaign_code,
                )
                if existing_refs.exists():
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 룰렛 쿠폰을 발급받았습니다.",
                            code="roulette_already_issued",
                        )

                referral = base_qs.create(
                    referrer=referee,
                    referee=referee,
                    code_used=ref_code,
                    campaign_code=campaign_code,
                    status="QUALIFIED",
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 룰렛 쿠폰을 발급받았습니다.",
                code="roulette_already_issued",
            )

    # 기말고사 이벤트 쿠폰 코드 처리
    if ref_code == "WOULDULIKEEX":
        # 이미 발급받은 쿠폰이 있는지 확인
        alias = router.db_for_write(Coupon)
        ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
        camp = Campaign.objects.using(alias).get(code="FINAL_EXAM_EVENT", active=True)
        
        existing_coupons = Coupon.objects.using(alias).filter(
            user=referee,
            coupon_type=ct,
            campaign=camp,
        )
        
        if existing_coupons.exists():
            raise ValidationError(
                "이미 기말고사 특별 쿠폰을 발급받았습니다.",
                code="final_exam_already_issued",
            )
        
        # 기말고사 쿠폰 발급
        result = issue_final_exam_coupons(referee)
        
        if result["already_issued"]:
            raise ValidationError(
                "이미 기말고사 특별 쿠폰을 발급받았습니다.",
                code="final_exam_already_issued",
            )
        
        # Referral을 생성하지 않고 None 반환 (특별 처리)
        # 하지만 API에서 Referral이 필요하므로, 가상의 Referral을 생성
        # referrer는 자기 자신으로 설정하되, campaign_code로 구분
        try:
            with transaction.atomic(using=db_alias):
                base_qs = Referral.objects.using(db_alias)
                locked_qs = base_qs.select_for_update()
                
                # 이미 기말고사 이벤트 Referral이 있는지 확인
                existing_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code="FINAL_EXAM_EVENT",
                )
                if existing_refs.exists():
                    # 쿠폰이 삭제되었는지 확인 (쿠폰이 없으면 Referral도 삭제하고 재입력 허용)
                    existing_ref = existing_refs.first()
                    existing_coupons = Coupon.objects.using(alias).filter(
                        user=referee,
                        coupon_type=ct,
                        campaign=camp,
                    )
                    
                    # 쿠폰이 없으면 Referral을 삭제하고 재입력 허용
                    if not existing_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 기말고사 특별 쿠폰을 발급받았습니다.",
                            code="final_exam_already_issued",
                        )
                
                # 특별한 Referral 생성 (referrer는 자기 자신, campaign_code로 구분)
                referral = base_qs.create(
                    referrer=referee,  # 자기 자신을 referrer로 설정 (campaign_code로 구분)
                    referee=referee,
                    code_used=ref_code,
                    campaign_code="FINAL_EXAM_EVENT",
                    status="QUALIFIED",  # 바로 QUALIFIED 상태로 설정
                    qualified_at=timezone.now(),
                )
                return referral, result["coupons"]
        except IntegrityError:
            raise ValidationError(
                "이미 기말고사 특별 쿠폰을 발급받았습니다.",
                code="final_exam_already_issued",
            )

    try:

        # coupons DB(cloudsql)에서 accounts_user(default)로 cross-DB JOIN이 발생하면
        # `accounts_user` 테이블이 없어서 500이 난다. (멀티 DB 환경에서 join 불가)
        # 따라서 InviteCode는 user_id만 가져오고, User는 default에서 별도로 로드한다.
        invite_code = (
            InviteCode.objects.using(db_alias)
            .only("id", "code", "user_id", "campaign_code")
            .get(code=ref_code)
        )
        referrer = User.objects.using("default").get(id=invite_code.user_id)

    except InviteCode.DoesNotExist:

        raise ValidationError("invalid referral code")
    except User.DoesNotExist:
        raise ValidationError("invalid referral code")

    if referrer.id == referee.id:

        raise ValidationError("self referral not allowed")

    try:

        with transaction.atomic(using=db_alias):

            base_qs = Referral.objects.using(db_alias)
            locked_qs = base_qs.select_for_update()
            
            # 운영진 계정의 추천코드인지 확인
            is_event_admin = _is_event_admin_user(referrer)
            
            # 사용된 추천코드의 campaign_code 확인 (위에서 조회한 invite_code 재사용)
            campaign_code = invite_code.campaign_code if is_event_admin and invite_code.campaign_code else None
            
            if is_event_admin and campaign_code:
                # 운영진 계정의 이벤트 추천코드인 경우
                # 같은 이벤트 Campaign의 추천코드를 이미 입력했는지 확인
                existing_event_refs = locked_qs.filter(
                    referee=referee,
                    campaign_code=campaign_code,
                )
                if existing_event_refs.exists():
                    # 쿠폰이 삭제되었는지 확인 (쿠폰이 없으면 Referral도 삭제하고 재입력 허용)
                    existing_ref = existing_event_refs.first()
                    coupon_alias = router.db_for_write(Coupon)
                    
                    # 해당 이벤트와 관련된 쿠폰 타입 확인
                    if campaign_code == "EVENT_REWARD_SIGNUP":
                        coupon_type_code = "WELCOME_3000"
                    elif campaign_code == "EVENT_REWARD_REFERRAL":
                        coupon_type_code = "REFERRAL_BONUS_REFEREE"
                    else:
                        coupon_type_code = None
                    
                    if coupon_type_code:
                        try:
                            ct = CouponType.objects.using(coupon_alias).get(code=coupon_type_code)
                            camp = Campaign.objects.using(coupon_alias).get(code=campaign_code, active=True)
                            related_coupons = Coupon.objects.using(coupon_alias).filter(
                                user=referee,
                                coupon_type=ct,
                                campaign=camp,
                            )
                            
                            # 쿠폰이 없으면 Referral을 삭제하고 재입력 허용
                            if not related_coupons.exists():
                                existing_ref.delete()
                            else:
                                raise ValidationError(
                                    "이미 해당 이벤트 추천코드를 입력했습니다.",
                                    code="event_referral_already_accepted",
                                )
                        except (CouponType.DoesNotExist, Campaign.DoesNotExist):
                            # 쿠폰 타입이나 캠페인을 찾을 수 없으면 Referral 삭제
                            existing_ref.delete()
                    else:
                        # 쿠폰 타입을 알 수 없으면 Referral 삭제
                        existing_ref.delete()
            else:
                # 일반 추천인 로직 (기말고사 이벤트 제외)
                existing_refs = locked_qs.filter(referee=referee, campaign_code__isnull=True)
                if existing_refs.exists():
                    # 쿠폰이 삭제되었는지 확인 (쿠폰이 없으면 Referral도 삭제하고 재입력 허용)
                    coupon_alias = router.db_for_write(Coupon)
                    existing_ref = existing_refs.first()
                    
                    # 해당 Referral과 관련된 쿠폰이 있는지 확인
                    related_coupons = Coupon.objects.using(coupon_alias).filter(
                        user=referee,
                        coupon_type__code__in=["REFERRAL_BONUS_REFEREE", "REFERRAL_BONUS_REFERRER"],
                    )
                    
                    # 쿠폰이 없으면 Referral을 삭제하고 재입력 허용
                    if not related_coupons.exists():
                        existing_ref.delete()
                    else:
                        raise ValidationError(
                            "이미 추천을 수락했습니다.",
                            code="referral_already_accepted",
                        )

                # 운영진 계정은 제한 없음
                if not is_event_admin:
                    active_referrals = (
                        locked_qs.filter(referrer=referrer, campaign_code__isnull=True)
                        .exclude(status="REJECTED")
                        .count()
                    )
                    if active_referrals >= REFERRAL_MAX_REWARDS_PER_REFERRER:

                        raise ValidationError(

                            "referral limit reached",

                            code="referral_limit_reached",

                        )

            referral = base_qs.create(
                referrer=referrer,
                referee=referee,
                code_used=ref_code,
                campaign_code=campaign_code,
            )
            # 같은 트랜잭션·락 안에서 PENDING → QUALIFIED 및 쿠폰 발급 (accept API에서 qualify 2차 호출 제거)
            _, issued_inline = _qualify_pending_referrals_locked(
                referee, locked_qs, db_alias
            )
            return referral, issued_inline

    except IntegrityError:

        raise ValidationError(

            "이미 추천을 수락했습니다.",

            code="referral_already_accepted",

        )


def _qualify_pending_referrals_locked(
    referee: User,
    locked_qs,
    db_alias: str,
) -> tuple[Referral | None, list]:
    """
    이미 select_for_update 된 Referral 쿼리셋 컨텍스트에서 PENDING 건을 QUALIFIED로 전환하고 쿠폰을 발급한다.
    accept_referral 내부와 qualify_referral_and_grant 양쪽에서 공통 사용.
    """
    issued_coupons: list = []
    pending_refs = locked_qs.filter(referee=referee, status="PENDING")

    if not pending_refs.exists():
        return None, []

    results = []
    for ref in pending_refs:
            # 기말고사 이벤트 쿠폰 처리
            if ref.campaign_code == "FINAL_EXAM_EVENT":
                # 이미 쿠폰이 발급되었는지 확인 (accept_referral에서 발급했을 수 있음)
                coupon_alias = router.db_for_write(Coupon)
                ct = CouponType.objects.using(coupon_alias).get(code="FINAL_EXAM_SPECIAL")
                camp = Campaign.objects.using(coupon_alias).get(code="FINAL_EXAM_EVENT", active=True)
                
                existing_coupons = Coupon.objects.using(coupon_alias).filter(
                    user=referee,
                    coupon_type=ct,
                    campaign=camp,
                )
                
                if not existing_coupons.exists():
                    result = issue_final_exam_coupons(referee)
                    issued_coupons.extend(result["coupons"])
                # 이미 QUALIFIED 상태로 설정되어 있을 수 있음
                if ref.status != "QUALIFIED":
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                results.append(ref)
                continue

            # 신학기 이벤트 쿠폰 처리 (accept_referral에서 이미 발급됨)
            if ref.campaign_code == "NEW_SEMESTER_EVENT":
                coupon_alias = router.db_for_write(Coupon)
                ct = CouponType.objects.using(coupon_alias).get(code="NEW_SEMESTER_SPECIAL")
                camp = Campaign.objects.using(coupon_alias).get(code="NEW_SEMESTER_EVENT", active=True)
                existing_coupons = Coupon.objects.using(coupon_alias).filter(
                    user=referee,
                    coupon_type=ct,
                    campaign=camp,
                )
                if not existing_coupons.exists():
                    result = issue_new_semester_coupons(referee)
                    issued_coupons.extend(result["coupons"])
                if ref.status != "QUALIFIED":
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                results.append(ref)
                continue

            # KNULIKE 이벤트 쿠폰 처리 (accept_referral에서 이미 발급됨)
            if ref.campaign_code == "KNULIKE_EVENT":
                coupon_alias = router.db_for_write(Coupon)
                ct = CouponType.objects.using(coupon_alias).get(code="KNULIKE")
                camp = Campaign.objects.using(coupon_alias).get(code="KNULIKE_EVENT", active=True)
                existing_coupons = Coupon.objects.using(coupon_alias).filter(
                    user=referee,
                    coupon_type=ct,
                    campaign=camp,
                )
                if not existing_coupons.exists():
                    result = issue_knulike_coupons(referee)
                    issued_coupons.extend(result["coupons"])
                if ref.status != "QUALIFIED":
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                results.append(ref)
                continue

            # DATELIKE 이벤트 쿠폰 처리 (accept_referral에서 이미 발급됨)
            if ref.campaign_code == "DATELIKE_EVENT":
                coupon_alias = router.db_for_write(Coupon)
                ct = CouponType.objects.using(coupon_alias).get(code="DATELIKE")
                camp = Campaign.objects.using(coupon_alias).get(code="DATELIKE_EVENT", active=True)
                existing_coupons = Coupon.objects.using(coupon_alias).filter(
                    user=referee,
                    coupon_type=ct,
                    campaign=camp,
                )
                if not existing_coupons.exists():
                    result = issue_datelike_coupons(referee)
                    issued_coupons.extend(result["coupons"])
                if ref.status != "QUALIFIED":
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                results.append(ref)
                continue

            # 운영진 계정인지 확인
            is_event_admin = _is_event_admin_user(ref.referrer)
            
            # 기획전: 운영진 추천코드(campaign_code 있음) → 18개 식당 전체 발급
            if is_event_admin and ref.campaign_code:
                campaign_code = ref.campaign_code
                coupon_type_code = "REFERRAL_BONUS_REFEREE"
                if campaign_code == "EVENT_REWARD_SIGNUP":
                    coupon_type_code = "WELCOME_3000"
                elif campaign_code == "EVENT_REWARD_REFERRAL":
                    coupon_type_code = "REFERRAL_BONUS_REFEREE"

                try:
                    event_coupons = _issue_event_reward_coupons(
                        user=referee,
                        campaign_code=campaign_code,
                        coupon_type_code=coupon_type_code,
                        code_used=ref.code_used,
                        db_alias=db_alias,
                    )
                    issued_coupons.extend(event_coupons)
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                    results.append(ref)
                    continue
                except (Campaign.DoesNotExist, CouponType.DoesNotExist) as e:
                    logger.error(
                        "이벤트 Campaign 또는 CouponType을 찾을 수 없습니다: %s, %s",
                        campaign_code,
                        e,
                    )
                    pass

            # 일반 추천인 로직
            current_reward_count = (
                locked_qs.filter(referrer=ref.referrer, status="QUALIFIED", campaign_code__isnull=True)
                .exclude(pk=ref.pk)
                .count()
            )
            can_reward_referrer = current_reward_count < REFERRAL_MAX_REWARDS_PER_REFERRER

            ref.status = "QUALIFIED"

            ref.qualified_at = timezone.now()

            ref.save(update_fields=["status", "qualified_at"], using=db_alias)

            # reward issuance - 한 식당씩만 발급 (추천인/피추천인 각 1개 식당)
            ref_ct = CouponType.objects.using(db_alias).get(code="REFERRAL_BONUS_REFERRER")
            ref_camp = Campaign.objects.using(db_alias).get(code="REFERRAL", active=True)
            new_ct = CouponType.objects.using(db_alias).get(code="REFERRAL_BONUS_REFEREE")

            if can_reward_referrer:
                ref_coupons = _issue_coupons_for_single_restaurant(
                    user=ref.referrer,
                    coupon_type=ref_ct,
                    campaign=ref_camp,
                    issue_key_prefix=f"REFERRAL_REFERRER:{ref.referrer_id}:{referee.id}",
                    db_alias=db_alias,
                )
                issued_coupons.extend(ref_coupons)

            referee_coupons = _issue_coupons_for_single_restaurant(
                user=referee,
                coupon_type=new_ct,
                campaign=ref_camp,
                issue_key_prefix=f"REFERRAL_REFEREE:{referee.id}",
                db_alias=db_alias,
            )
            issued_coupons.extend(referee_coupons)
            results.append(ref)

    return (results[0] if results else None, issued_coupons)


def qualify_referral_and_grant(referee: User) -> tuple[Referral | None, list]:
    db_alias = router.db_for_write(Referral)

    with transaction.atomic(using=db_alias):
        locked_qs = Referral.objects.using(db_alias).select_for_update()

        first, issued = _qualify_pending_referrals_locked(referee, locked_qs, db_alias)

        if first is None and not issued:
            existing_refs = Referral.objects.using(db_alias).filter(referee=referee)
            return (existing_refs.first() if existing_refs.exists() else None, [])

        return (first, issued)


def claim_flash_drop(user: User, campaign_code: str, idem_key: str) -> Coupon:
    cache_key = f"idem:{idem_key}"
    prev = idem_get(cache_key)
    if prev:
        alias = router.db_for_read(Coupon)
        return Coupon.objects.using(alias).get(user=user, code=prev)

    coupon_alias = router.db_for_write(Coupon)
    camp = Campaign.objects.using(coupon_alias).get(code=campaign_code, active=True)
    quota_key = f"quota:{camp.id}:{date.today():%Y%m%d}"
    cli = __import__("django_redis").get_redis_connection()

    with redis_lock(f"lock:flash:{camp.id}", ttl=3):
        remaining = cli.decr(quota_key)
        if remaining < 0:
            cli.incr(quota_key)  # 복원
            raise ValidationError("sold out")

        ct = CouponType.objects.using(coupon_alias).get(code="FLASH_3000")
        coupon = _create_coupon_with_restaurant(
            user=user,
            coupon_type=ct,
            campaign=camp,
            issue_key=f"FLASH:{camp.id}:{user.id}:{date.today():%Y%m%d}",
            db_alias=coupon_alias,
        )
    idem_set(cache_key, coupon.code, ttl=300)
    return coupon




# ---- Stamp (Punch) Card Service ----

# 레거시 기본값 (규칙 없을 때 폴백)
STAMP_LEGACY_THRESHOLDS = (5, 10)
STAMP_LEGACY_CYCLE_TARGET = 10
STAMP_LEGACY_REWARD_CODES = {
    5: "STAMP_REWARD_5",
    10: "STAMP_REWARD_10",
}
REWARD_CAMPAIGN_CODE = "STAMP_REWARD"
STAMP_DAILY_EARN_LIMIT = int(os.getenv("STAMP_DAILY_EARN_LIMIT", "5"))

STAMP_DB_ALIAS = "cloudsql"


def _get_stamp_reward_rule(restaurant_id: int) -> StampRewardRule | None:
    """식당별 스탬프 보상 규칙 조회. 없으면 None."""
    try:
        return StampRewardRule.objects.using(STAMP_DB_ALIAS).get(
            restaurant_id=restaurant_id, active=True
        )
    except StampRewardRule.DoesNotExist:
        return None


def _get_legacy_config() -> dict:
    """레거시(5, 10) 규칙용 config."""
    return {
        "thresholds": [
            {"stamps": 5, "coupon_type_code": "STAMP_REWARD_5"},
            {"stamps": 10, "coupon_type_code": "STAMP_REWARD_10"},
        ],
        "cycle_target": 10,
    }


def _get_cycle_target_for_restaurant(restaurant_id: int) -> int:
    """식당별 cycle_target 반환 (규칙 없으면 10)."""
    rule = _get_stamp_reward_rule(restaurant_id)
    if rule and rule.config_json:
        return rule.config_json.get("cycle_target", 10)
    return STAMP_LEGACY_CYCLE_TARGET


def _build_rewards_for_restaurants_batch(
    restaurant_ids: set[int],
    rule_map: dict[int, StampRewardRule],
    ct_map: dict[str, CouponType],
    benefit_map: dict[tuple[int, str], dict],
) -> dict[int, list[dict]]:
    """
    식당 ID 목록에 대해 rewards를 배치로 생성.
    rule_map, ct_map, benefit_map은 이미 프리페치된 데이터.
    반환: {restaurant_id: [reward_dict, ...]}
    """
    legacy_config = _get_legacy_config()
    result: dict[int, list[dict]] = {}

    for restaurant_id in restaurant_ids:
        rule = rule_map.get(restaurant_id)
        if not rule:
            config = legacy_config
            rule_type = "THRESHOLD"
        else:
            config = rule.config_json
            rule_type = rule.rule_type

        rewards: list[dict] = []
        restaurant_benefit_map: dict[str, dict] = {}
        if rule_type == "THRESHOLD":
            coupon_codes = [t["coupon_type_code"] for t in config.get("thresholds", [])]
        else:
            coupon_codes = [r["coupon_type_code"] for r in config.get("ranges", [])]

        for code in coupon_codes:
            b = benefit_map.get((restaurant_id, code))
            if b:
                restaurant_benefit_map[code] = {
                    "title": b.get("title", ""),
                    "subtitle": b.get("subtitle", ""),
                    "notes": b.get("notes", ""),
                    "benefit": b.get("benefit", {}),
                }

        if rule_type == "THRESHOLD":
            for t in sorted(config.get("thresholds", []), key=lambda x: x["stamps"]):
                code = t["coupon_type_code"]
                b = restaurant_benefit_map.get(code, {})
                ct = ct_map.get(code)
                default_benefit = ct.benefit_json if ct else {}
                rewards.append({
                    "stamps": t["stamps"],
                    "title": b.get("title") or (ct.title if ct else code),
                    "subtitle": b.get("subtitle", ""),
                    "notes": b.get("notes", ""),
                    "benefit": b.get("benefit") or default_benefit,
                    "coupon_type_code": code,
                })
        else:
            for r in config.get("ranges", []):
                min_v, max_v = r.get("min_visit"), r.get("max_visit")
                code = r.get("coupon_type_code")
                if min_v is None or max_v is None or not code:
                    continue
                b = restaurant_benefit_map.get(code, {})
                ct = ct_map.get(code)
                default_benefit = ct.benefit_json if ct else {}
                key = f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
                rewards.append({
                    "visit_range": key,
                    "min_visit": min_v,
                    "max_visit": max_v,
                    "title": b.get("title") or (ct.title if ct else code),
                    "subtitle": b.get("subtitle", ""),
                    "notes": b.get("notes", ""),
                    "benefit": b.get("benefit") or default_benefit,
                    "coupon_type_code": code,
                })
        result[restaurant_id] = rewards

    return result


def get_stamp_rewards_for_restaurant(restaurant_id: int) -> list[dict]:
    """
    식당별 스탬프 적립 시 발급되는 쿠폰 목록 반환.
    프론트에서 "N개 적립 시 ~ 혜택" 표시용.
    """
    alias = STAMP_DB_ALIAS
    rule = _get_stamp_reward_rule(restaurant_id)

    if not rule:
        config = _get_legacy_config()
        rule_type = "THRESHOLD"
    else:
        config = rule.config_json
        rule_type = rule.rule_type

    rewards: list[dict] = []
    benefit_map: dict[str, dict] = {}

    if rule_type == "THRESHOLD":
        thresholds = config.get("thresholds", [])
        coupon_codes = [t["coupon_type_code"] for t in thresholds]
    else:
        ranges = config.get("ranges", [])
        coupon_codes = [r["coupon_type_code"] for r in ranges]

    if coupon_codes:
        benefits = RestaurantCouponBenefit.objects.using(alias).filter(
            restaurant_id=restaurant_id,
            coupon_type__code__in=coupon_codes,
            active=True,
        ).select_related("coupon_type")
        for b in benefits:
            benefit_map[b.coupon_type.code] = {
                "title": b.title,
                "subtitle": b.subtitle,
                "notes": b.notes or "",
                "benefit": b.benefit_json or {},
            }

    if rule_type == "THRESHOLD":
        for t in sorted(config.get("thresholds", []), key=lambda x: x["stamps"]):
            code = t["coupon_type_code"]
            b = benefit_map.get(code, {})
            ct = CouponType.objects.using(alias).filter(code=code).first()
            default_benefit = ct.benefit_json if ct else {}
            rewards.append({
                "stamps": t["stamps"],
                "title": b.get("title") or (ct.title if ct else code),
                "subtitle": b.get("subtitle", ""),
                "notes": b.get("notes", ""),
                "benefit": b.get("benefit") or default_benefit,
                "coupon_type_code": code,
            })
    else:
        for r in config.get("ranges", []):
            min_v, max_v = r.get("min_visit"), r.get("max_visit")
            code = r.get("coupon_type_code")
            if min_v is None or max_v is None or not code:
                continue
            b = benefit_map.get(code, {})
            ct = CouponType.objects.using(alias).filter(code=code).first()
            default_benefit = ct.benefit_json if ct else {}
            key = f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
            rewards.append({
                "visit_range": key,
                "min_visit": min_v,
                "max_visit": max_v,
                "title": b.get("title") or (ct.title if ct else code),
                "subtitle": b.get("subtitle", ""),
                "notes": b.get("notes", ""),
                "benefit": b.get("benefit") or default_benefit,
                "coupon_type_code": code,
            })

    return rewards


def _verify_pin(restaurant_id: int, pin: str) -> bool:
    try:
        mp = MerchantPin.objects.select_related("restaurant").get(restaurant_id=restaurant_id)
    except MerchantPin.DoesNotExist:
        return False

    if mp.algo == "STATIC":
        return pin == mp.secret
    # For TOTP, integrate pyotp in actual deployment.
    # import pyotp
    # return pyotp.TOTP(mp.secret, interval=mp.period_sec).verify(pin)
    return False


def _issue_reward_coupon(
    user: User,
    restaurant_id: int,
    *,
    coupon_type_code: str,
    issue_key_suffix: str,
    stamp_subtitle: str = "",
    db_alias: str | None = None,
) -> "Coupon | None":
    """
    스탬프 보상 쿠폰 발급.
    restaurant_id가 쿠폰 발급 대상(제휴+benefit+비제외)이 아니면 None 반환(발급 스킵).
    """
    alias = db_alias or router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code=coupon_type_code)
    valid_ids = _get_valid_restaurant_ids_for_coupon_type(ct, db_alias=alias)
    if restaurant_id not in valid_ids:
        logger.warning(
            "Stamp reward coupon skipped: restaurant_id=%s not in valid targets (affiliate+benefit) for %s",
            restaurant_id,
            coupon_type_code,
        )
        return None

    camp = Campaign.objects.using(alias).get(code=REWARD_CAMPAIGN_CODE, active=True)
    issue_key = f"STAMP_REWARD:{user.id}:{issue_key_suffix}"
    expires_at = _resolve_coupon_expiry_for_issue(ct)
    benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, db_alias=alias)
    if benefit_snapshot:
        # 스탬프 비고(notes)는 발급 쿠폰에 포함하지 않음
        # subtitle에 몇 개 혜택 쿠폰인지 명시 (예: "3개 스탬프 보상")
        benefit_snapshot = {
            **benefit_snapshot,
            "notes": "",
            "subtitle": stamp_subtitle or benefit_snapshot.get("subtitle", ""),
        }
    return Coupon.objects.using(alias).create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        restaurant_id=restaurant_id,
        expires_at=expires_at,
        issue_key=issue_key,
        benefit_snapshot=benefit_snapshot,
    )


@transaction.atomic(using=STAMP_DB_ALIAS)
def add_stamp(
    user: User,
    restaurant_id: int,
    pin: str,
    idem_key: str | None = None,
    count: int = 1,
):
    if count < 1 or count > 4:
        raise ValidationError(
            "stamp count must be between 1 and 4",
            code="invalid_stamp_count",
        )

    # 멱등(같은 요청 재발급 방지)
    if idem_key:
        cache_key = f"idem:stamp:{restaurant_id}:{count}:{idem_key}"
        prev = idem_get(cache_key)
        if prev:
            return prev

    # 매장 코드 검증
    if not _verify_pin(restaurant_id, pin):
        raise ValidationError("invalid merchant code")

    # 동시 요청 방지 (사용자 단위 잠금: 일일 적립 제한 우회 방지)
    lock_key = f"lock:stamp:{user.id}"
    with redis_lock(lock_key, ttl=5):
        if STAMP_DAILY_EARN_LIMIT > 0:
            today = timezone.localdate()
            today_start = timezone.make_aware(datetime.combine(today, time.min))
            tomorrow_start = today_start + timedelta(days=1)
            earned_today = (
                StampEvent.objects.using(STAMP_DB_ALIAS)
                .filter(
                    user=user,
                    restaurant_id=restaurant_id,
                    delta__gt=0,
                    created_at__gte=today_start,
                    created_at__lt=tomorrow_start,
                )
                .aggregate(total=Sum("delta"))
                .get("total")
            )
            earned_today = int(earned_today or 0)
            if earned_today + count > STAMP_DAILY_EARN_LIMIT:
                raise ValidationError(
                    f"daily stamp limit reached for this restaurant ({STAMP_DAILY_EARN_LIMIT}/day)",
                    code="stamp_daily_limit_reached",
                )

        wallet, _ = StampWallet.objects.using(STAMP_DB_ALIAS).get_or_create(
            user=user, restaurant_id=restaurant_id
        )

        StampEvent.objects.using(STAMP_DB_ALIAS).create(
            user=user, restaurant_id=restaurant_id, delta=+count, source="PIN"
        )

        # 규칙 조회 (없으면 레거시 5, 10 사용)
        rule = _get_stamp_reward_rule(restaurant_id)
        if rule:
            rule_type = rule.rule_type
            config = rule.config_json
            cycle_target = config.get("cycle_target", 10)
        else:
            rule_type = "THRESHOLD"
            config = _get_legacy_config()
            cycle_target = STAMP_LEGACY_CYCLE_TARGET

        # 방어: 잘못 저장된 config_json로 인해 "만땅인데 보상 미발급 + 만땅 유지"가 발생하지 않도록 보정
        # - THRESHOLD인데 thresholds가 비어있으면 cycle_target을 단일 threshold로 간주
        # - cycle_target이 비정상(<=0)이면 레거시로 폴백
        if not isinstance(cycle_target, int) or cycle_target <= 0:
            rule_type = "THRESHOLD"
            config = _get_legacy_config()
            cycle_target = STAMP_LEGACY_CYCLE_TARGET

        reward_codes = []
        reward_details = []
        now_suffix = timezone.now().strftime("%Y%m%d%H%M%S%f")

        if rule_type == "THRESHOLD":
            thresholds = config.get("thresholds", []) if isinstance(config, dict) else []
            if not thresholds:
                thresholds = [
                    {
                        "stamps": cycle_target,
                        "coupon_type_code": f"STAMP_REWARD_{cycle_target}",
                    }
                ]

            threshold_stamps = sorted(int(t["stamps"]) for t in thresholds if t.get("stamps") is not None)
            max_threshold = max(threshold_stamps) if threshold_stamps else 0

            for step_idx in range(1, count + 1):
                before_stamps = wallet.stamps
                wallet.stamps += 1
                crossed_max_threshold = False

                for t in thresholds:
                    th = int(t["stamps"])
                    coupon_type_code = t.get("coupon_type_code")
                    if not coupon_type_code:
                        raise ValidationError(
                            f"stamp reward coupon type missing for threshold={th}"
                        )
                    if before_stamps < th <= wallet.stamps:
                        suffix = f"{restaurant_id}:{now_suffix}:N{step_idx}:T{th}"
                        reward = _issue_reward_coupon(
                            user,
                            restaurant_id,
                            coupon_type_code=coupon_type_code,
                            issue_key_suffix=suffix,
                            stamp_subtitle=f"{th}개 스탬프 보상",
                            db_alias=STAMP_DB_ALIAS,
                        )
                        if reward:
                            logger.info(
                                "Stamp reward issued user=%s restaurant=%s threshold=%s coupon_type=%s coupon_code=%s",
                                user.id,
                                restaurant_id,
                                th,
                                reward.coupon_type.code,
                                reward.code,
                            )
                            reward_codes.append(reward.code)
                            reward_details.append(
                                {
                                    "threshold": th,
                                    "coupon_code": reward.code,
                                    "coupon_type": reward.coupon_type.code,
                                }
                            )
                        if th == max_threshold:
                            crossed_max_threshold = True

                # 배치 적립 시에도 "1개씩 적립한 것과 동일"하게 라운드 리셋 처리
                if crossed_max_threshold:
                    wallet.stamps -= cycle_target

        else:  # VISIT
            ranges = config.get("ranges", [])
            for step_idx in range(1, count + 1):
                wallet.stamps += 1
                visit_number = wallet.stamps

                for r in ranges:
                    min_v = r.get("min_visit")
                    max_v = r.get("max_visit")
                    coupon_type_code = r.get("coupon_type_code")
                    if min_v is None or max_v is None or not coupon_type_code:
                        continue
                    if min_v <= visit_number <= max_v:
                        suffix = f"{restaurant_id}:{now_suffix}:N{step_idx}:V{visit_number}"
                        visit_subtitle = (
                            f"{visit_number}회 방문 보상"
                            if min_v == max_v
                            else f"{min_v}~{max_v}회 방문 보상"
                        )
                        reward = _issue_reward_coupon(
                            user,
                            restaurant_id,
                            coupon_type_code=coupon_type_code,
                            issue_key_suffix=suffix,
                            stamp_subtitle=visit_subtitle,
                            db_alias=STAMP_DB_ALIAS,
                        )
                        if reward:
                            logger.info(
                                "Stamp visit reward issued user=%s restaurant=%s visit=%s coupon_type=%s coupon_code=%s",
                                user.id,
                                restaurant_id,
                                visit_number,
                                reward.coupon_type.code,
                                reward.code,
                            )
                            reward_codes.append(reward.code)
                            reward_details.append(
                                {
                                    "visit": visit_number,
                                    "coupon_code": reward.code,
                                    "coupon_type": reward.coupon_type.code,
                                }
                            )
                        break

                if visit_number >= cycle_target:
                    wallet.stamps -= cycle_target

        wallet.save()

    result = {
        "ok": True,
        "current": wallet.stamps,
        "target": cycle_target,
        "added": count,
        "reward_coupon_code": reward_codes[-1] if reward_codes else None,
    }
    if reward_codes:
        result["reward_coupon_codes"] = reward_codes
        result["reward_coupons"] = reward_details
    if idem_key:
        idem_set(cache_key, result, ttl=300)
    return result



def get_all_stamp_statuses(
    user: User,
    *,
    limit_to_restaurant_ids: set[int] | None = None,
):
    """
    전체 제휴식당 스탬프 현황 조회.

    limit_to_restaurant_ids:
        지정 시 해당 식당 ID만 집계·응답 (전체 제휴 목록 조회 생략).
        적립 진행 중(stamps>0) 식당만 필요할 때 `in_progress_only` API와 함께 사용하면 부하·페이로드가 크게 줄어듦.
    """
    restaurant_alias = router.db_for_read(AffiliateRestaurant)
    if limit_to_restaurant_ids is not None:
        if not limit_to_restaurant_ids:
            return []
        accessible_ids = sorted(limit_to_restaurant_ids)
    else:
        try:
            accessible_ids = list(
                AffiliateRestaurant.objects.using(restaurant_alias)
                .order_by("restaurant_id")
                .values_list("restaurant_id", flat=True)
            )
        except DatabaseError:
            accessible_ids = []

    wallet_qs = StampWallet.objects.using(STAMP_DB_ALIAS).filter(user=user)
    if limit_to_restaurant_ids is not None:
        wallet_qs = wallet_qs.filter(restaurant_id__in=limit_to_restaurant_ids)
    wallet_map = {wallet.restaurant_id: wallet for wallet in wallet_qs}

    all_rids = set(accessible_ids) | set(wallet_map.keys())
    rule_qs = StampRewardRule.objects.using(STAMP_DB_ALIAS).filter(
        restaurant_id__in=all_rids, active=True
    )
    rule_map = {r.restaurant_id: r for r in rule_qs}
    target_map = {r.restaurant_id: r.config_json.get("cycle_target", 10) for r in rule_qs}
    notes_map = {r.restaurant_id: (r.config_json.get("notes") or "") for r in rule_qs}

    # 배치 프리페치: rewards 생성에 필요한 CouponType, RestaurantCouponBenefit
    rewards_map: dict[int, list[dict]] = {}
    if all_rids:
        alias = STAMP_DB_ALIAS
        legacy_config = _get_legacy_config()
        all_codes = {t["coupon_type_code"] for t in legacy_config["thresholds"]}
        for rule in rule_map.values():
            cfg = rule.config_json
            if rule.rule_type == "THRESHOLD":
                for t in cfg.get("thresholds", []):
                    all_codes.add(t.get("coupon_type_code"))
            else:
                for r in cfg.get("ranges", []):
                    all_codes.add(r.get("coupon_type_code"))
        all_codes.discard(None)

        ct_map = {ct.code: ct for ct in CouponType.objects.using(alias).filter(code__in=all_codes)}

        benefits_qs = RestaurantCouponBenefit.objects.using(alias).filter(
            restaurant_id__in=all_rids,
            coupon_type__code__in=all_codes,
            active=True,
        ).select_related("coupon_type")
        benefit_map = {}
        for b in benefits_qs:
            benefit_map[(b.restaurant_id, b.coupon_type.code)] = {
                "title": b.title,
                "subtitle": b.subtitle or "",
                "notes": b.notes or "",
                "benefit": b.benefit_json or {},
            }

        rewards_map = _build_rewards_for_restaurants_batch(
            all_rids, rule_map, ct_map, benefit_map
        )

    def _target(rid: int) -> int:
        return target_map.get(rid, STAMP_LEGACY_CYCLE_TARGET)

    def _notes(rid: int) -> str:
        return notes_map.get(rid, "")

    results: list[dict] = []
    seen_ids: set[int] = set()

    for restaurant_id in accessible_ids:
        wallet = wallet_map.get(restaurant_id)
        results.append(
            {
                "restaurant_id": restaurant_id,
                "current": wallet.stamps if wallet else 0,
                "target": _target(restaurant_id),
                "rewards": rewards_map.get(restaurant_id, []),
                "notes": _notes(restaurant_id),
                "updated_at": wallet.updated_at if wallet else None,
            }
        )
        seen_ids.add(restaurant_id)

    extra_ids = sorted(set(wallet_map.keys()) - seen_ids)
    for restaurant_id in extra_ids:
        wallet = wallet_map[restaurant_id]
        results.append(
            {
                "restaurant_id": restaurant_id,
                "current": wallet.stamps,
                "target": _target(restaurant_id),
                "rewards": rewards_map.get(restaurant_id, []),
                "notes": _notes(restaurant_id),
                "updated_at": wallet.updated_at,
            }
        )

    return results


def get_active_affiliate_restaurant_ids_for_user(user: User) -> list[int]:
    """사용자 기준 진행 중 제휴식당 ID 목록 반환."""
    now = timezone.now()
    coupon_alias = router.db_for_read(Coupon)
    stamp_alias = router.db_for_read(StampWallet)

    coupon_ids = (
        Coupon.objects.using(coupon_alias)
        .filter(
            user=user,
            status="ISSUED",
            expires_at__gte=now,
            restaurant_id__isnull=False,
        )
        .values_list("restaurant_id", flat=True)
        .distinct()
    )
    stamp_ids = (
        StampWallet.objects.using(stamp_alias)
        .filter(user=user, stamps__gt=0)
        .values_list("restaurant_id", flat=True)
        .distinct()
    )

    return sorted(set(coupon_ids) | set(stamp_ids))


def get_stamp_status(user: User, restaurant_id: int):
    target = _get_cycle_target_for_restaurant(restaurant_id)
    rewards = get_stamp_rewards_for_restaurant(restaurant_id)
    rule = _get_stamp_reward_rule(restaurant_id)
    notes = (rule.config_json.get("notes", "") or "") if rule else ""
    try:
        w = StampWallet.objects.using(STAMP_DB_ALIAS).get(user=user, restaurant_id=restaurant_id)
        return {
            "current": w.stamps,
            "target": target,
            "rewards": rewards,
            "notes": notes,
            "updated_at": w.updated_at,
        }
    except StampWallet.DoesNotExist:
        return {"current": 0, "target": target, "rewards": rewards, "notes": notes, "updated_at": None}
