import uuid
import random
import logging
import os
from datetime import date, datetime
from django.db import transaction, IntegrityError, router, DatabaseError
from django.db.models import Count
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
    RestaurantCouponBenefit,
)
from .utils import make_coupon_code, redis_lock, idem_get, idem_set


User = get_user_model()

logger = logging.getLogger(__name__)


GLOBAL_COUPON_EXPIRY = datetime(2027, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
REFERRAL_MAX_REWARDS_PER_REFERRER = 5

# 운영진 계정 카카오 ID 목록 (환경 변수에서 읽어옴, 쉼표로 구분)
EVENT_ADMIN_KAKAO_IDS = set(
    int(kid.strip())
    for kid in os.getenv("EVENT_ADMIN_KAKAO_IDS", "").split(",")
    if kid.strip()
)


def _is_event_admin_user(user: User) -> bool:
    """운영진 계정인지 확인"""
    return user.kakao_id in EVENT_ADMIN_KAKAO_IDS


MAX_COUPONS_PER_RESTAURANT = 200

COUPON_TYPE_EXCLUDED_RESTAURANTS: dict[str, set[int]] = {
    "WELCOME_3000": {30},
    "REFERRAL_BONUS_REFERRER": {30},
    "REFERRAL_BONUS_REFEREE": {30},
    "FINAL_EXAM_SPECIAL": {30},  # 고니식탁 제외
}


def _build_benefit_snapshot(
    coupon_type: CouponType,
    restaurant_id: int,
    *,
    db_alias: str | None = None,
) -> dict:
    snapshot = {
        "coupon_type_code": coupon_type.code,
        "coupon_type_title": coupon_type.title,
        "restaurant_id": restaurant_id,
        "benefit": coupon_type.benefit_json,
        "title": coupon_type.title,
        "subtitle": "",
    }

    benefit_alias = db_alias or router.db_for_read(RestaurantCouponBenefit)
    benefit = (
        RestaurantCouponBenefit.objects.using(benefit_alias)
        .select_related("restaurant")
        .filter(
            coupon_type=coupon_type,
            restaurant_id=restaurant_id,
            active=True,
        )
        .first()
    )

    if benefit:
        snapshot.update(
            {
                "title": benefit.title,
                "subtitle": benefit.subtitle,
                "benefit": benefit.benefit_json or coupon_type.benefit_json,
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
        return snapshot

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
    alias = db_alias or router.db_for_write(Coupon)
    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias).values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")

    excluded_ids = COUPON_TYPE_EXCLUDED_RESTAURANTS.get(ct.code, set())

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

def _expires_at(ct: CouponType):
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



def issue_signup_coupon(user: User):
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="WELCOME_3000")
    camp = Campaign.objects.using(alias).get(code="SIGNUP_WELCOME", active=True)
    issue_key = f"SIGNUP:{user.id}"
    return _create_coupon_with_restaurant(
        user=user,
        coupon_type=ct,
        campaign=camp,
        issue_key=issue_key,
        db_alias=alias,
    )


@transaction.atomic
def issue_ambassador_coupons(user: User):
    """
    엠버서더 보상을 위해 특정 사용자에게 전체 제휴식당 쿠폰을 발급합니다.
    신규가입 쿠폰과 동일한 쿠폰 타입(WELCOME_3000)을 사용하지만,
    각 식당마다 고유한 issue_key를 사용하여 중복 발급 방지 제약조건을 통과합니다.
    
    Args:
        user: 쿠폰을 발급받을 사용자
        
    Returns:
        발급된 쿠폰 리스트
    """
    alias = router.db_for_write(Coupon)
    ct = CouponType.objects.using(alias).get(code="WELCOME_3000")
    camp = Campaign.objects.using(alias).get(code="SIGNUP_WELCOME", active=True)
    
    # 전체 제휴식당 목록 가져오기
    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias).values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")
    
    # 제외된 식당 필터링
    excluded_ids = COUPON_TYPE_EXCLUDED_RESTAURANTS.get(ct.code, set())
    valid_restaurant_ids = [rid for rid in restaurant_ids if rid not in excluded_ids]
    
    if not valid_restaurant_ids:
        raise ValidationError("no valid restaurants available after exclusions")
    
    issued_coupons = []
    failed_restaurants = []
    
    for restaurant_id in valid_restaurant_ids:
        try:
            # 각 식당마다 고유한 issue_key 사용
            issue_key = f"AMBASSADOR:{user.id}:{restaurant_id}"
            
            # 이미 발급된 쿠폰이 있는지 확인 (중복 발급 방지)
            existing = Coupon.objects.using(alias).filter(
                user=user,
                coupon_type=ct,
                campaign=camp,
                issue_key=issue_key,
            ).first()
            
            if existing:
                logger.info(
                    f"Coupon already exists for ambassador reward - "
                    f"user={user.id}, restaurant={restaurant_id}, coupon_code={existing.code}"
                )
                issued_coupons.append(existing)
                continue
            
            # 쿠폰 생성
            benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id, db_alias=alias)
            # 엠버서더 쿠폰의 subtitle을 '엠버서더 특별 쿠폰'으로 설정
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
            logger.info(
                f"Ambassador coupon issued - "
                f"user={user.id}, restaurant={restaurant_id}, coupon_code={coupon.code}"
            )
        except Exception as exc:
            logger.error(
                f"Failed to issue ambassador coupon - "
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
    }


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
    
    # 전체 제휴식당 목록 가져오기
    restaurant_ids = list(
        AffiliateRestaurant.objects.using(alias).values_list("restaurant_id", flat=True)
    )
    if not restaurant_ids:
        raise ValidationError("no restaurants available for coupon assignment")
    
    # 제외된 식당 필터링
    excluded_ids = COUPON_TYPE_EXCLUDED_RESTAURANTS.get(ct.code, set())
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
    }



def accept_referral(*, referee: User, ref_code: str) -> Referral:

    db_alias = router.db_for_write(Referral)

    # 차단된 쿠폰 코드 목록
    BLOCKED_CODES = {"01KBWVFS", "01KBWVFSSNEE"}
    
    if ref_code.upper() in BLOCKED_CODES:
        raise ValidationError("invalid referral code")
    
    # 기말고사 이벤트 쿠폰 코드 처리
    if ref_code.upper() == "WOULDULIKEEX":
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
                return base_qs.create(
                    referrer=referee,  # 자기 자신을 referrer로 설정 (campaign_code로 구분)
                    referee=referee,
                    code_used=ref_code.upper(),
                    campaign_code="FINAL_EXAM_EVENT",
                    status="QUALIFIED",  # 바로 QUALIFIED 상태로 설정
                    qualified_at=timezone.now(),
                )
        except IntegrityError:
            raise ValidationError(
                "이미 기말고사 특별 쿠폰을 발급받았습니다.",
                code="final_exam_already_issued",
            )

    try:

        invite_code = InviteCode.objects.using(db_alias).get(code=ref_code)

        referrer = invite_code.user

    except InviteCode.DoesNotExist:

        raise ValidationError("invalid referral code")

    if referrer.id == referee.id:

        raise ValidationError("self referral not allowed")

    try:

        with transaction.atomic(using=db_alias):

            base_qs = Referral.objects.using(db_alias)
            locked_qs = base_qs.select_for_update()
            
            # 운영진 계정의 추천코드인지 확인
            is_event_admin = _is_event_admin_user(referrer)
            
            # 사용된 추천코드의 campaign_code 확인
            invite_code = InviteCode.objects.using(db_alias).get(code=ref_code)
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

            return base_qs.create(

                referrer=referrer,

                referee=referee,

                code_used=ref_code,
                campaign_code=campaign_code,

            )

    except IntegrityError:

        raise ValidationError(

            "이미 추천을 수락했습니다.",

            code="referral_already_accepted",

        )

def qualify_referral_and_grant(referee: User):

    # referee 가???료 ?점 ?에??출

    db_alias = router.db_for_write(Referral)

    with transaction.atomic(using=db_alias):

        locked_qs = Referral.objects.using(db_alias).select_for_update()

        # PENDING 상태인 모든 Referral 처리 (이벤트와 일반 모두)
        pending_refs = locked_qs.filter(referee=referee, status="PENDING")
        
        if not pending_refs.exists():
            # 이미 처리된 Referral이 있는지 확인
            existing_refs = Referral.objects.using(db_alias).filter(referee=referee)
            return existing_refs.first() if existing_refs.exists() else None
        
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
                    # 쿠폰이 없으면 발급
                    issue_final_exam_coupons(referee)
                
                # 이미 QUALIFIED 상태로 설정되어 있을 수 있음
                if ref.status != "QUALIFIED":
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                results.append(ref)
                continue
            
            # 운영진 계정인지 확인
            is_event_admin = _is_event_admin_user(ref.referrer)
            
            # 운영진 계정이면 이벤트 보상 Campaign 사용
            if is_event_admin and ref.campaign_code:
                # campaign_code로 Campaign 결정
                campaign_code = ref.campaign_code
                coupon_type_code = "REFERRAL_BONUS_REFEREE"
                
                if campaign_code == "EVENT_REWARD_SIGNUP":
                    coupon_type_code = "WELCOME_3000"
                elif campaign_code == "EVENT_REWARD_REFERRAL":
                    coupon_type_code = "REFERRAL_BONUS_REFEREE"
                
                try:
                    event_camp = Campaign.objects.using(db_alias).get(code=campaign_code, active=True)
                    event_ct = CouponType.objects.using(db_alias).get(code=coupon_type_code)
                    
                    # 이벤트 보상 쿠폰 발급 (referee에게만)
                    _create_coupon_with_restaurant(
                        user=referee,
                        coupon_type=event_ct,
                        campaign=event_camp,
                        issue_key=f"EVENT_REWARD:{referee.id}:{ref.code_used}",
                        db_alias=db_alias,
                    )
                    
                    ref.status = "QUALIFIED"
                    ref.qualified_at = timezone.now()
                    ref.save(update_fields=["status", "qualified_at"], using=db_alias)
                    results.append(ref)
                    continue
                except (Campaign.DoesNotExist, CouponType.DoesNotExist) as e:
                    logger.error(f"이벤트 Campaign 또는 CouponType을 찾을 수 없습니다: {campaign_code}, {e}")
                    # 일반 로직으로 폴백
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

            # reward issuance

            ref_ct = CouponType.objects.using(db_alias).get(code="REFERRAL_BONUS_REFERRER")

            ref_camp = Campaign.objects.using(db_alias).get(code="REFERRAL", active=True)



            if can_reward_referrer:
                _create_coupon_with_restaurant(
                    user=ref.referrer,
                    coupon_type=ref_ct,
                    campaign=ref_camp,
                    issue_key=f"REFERRAL_REFERRER:{ref.referrer_id}:{referee.id}",
                    db_alias=db_alias,
                )

            new_ct = CouponType.objects.using(db_alias).get(code="REFERRAL_BONUS_REFEREE")

            _create_coupon_with_restaurant(
                user=referee,
                coupon_type=new_ct,
                campaign=ref_camp,
                issue_key=f"REFERRAL_REFEREE:{referee.id}",
                db_alias=db_alias,
            )
            results.append(ref)
        
        return results[0] if results else None



def claim_flash_drop(user: User, campaign_code: str, idem_key: str):
    cache_key = f"idem:{idem_key}"
    prev = idem_get(cache_key)
    if prev:
        return prev



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
    return coupon.code




# ---- Stamp (Punch) Card Service ----

# 목표 개수 및 보상 정의 (시드로 생성 필요)
STAMP_THRESHOLDS = (5, 10)
STAMP_CYCLE_TARGET = max(STAMP_THRESHOLDS)
REWARD_COUPON_CODES = {
    5: "STAMP_REWARD_5",
    10: "STAMP_REWARD_10",
}
REWARD_CAMPAIGN_CODE = "STAMP_REWARD"


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
):
    ct = CouponType.objects.get(code=coupon_type_code)
    camp = Campaign.objects.get(code=REWARD_CAMPAIGN_CODE, active=True)
    issue_key = f"STAMP_REWARD:{user.id}:{issue_key_suffix}"
    expires_at = _expires_at(ct)
    benefit_snapshot = _build_benefit_snapshot(ct, restaurant_id)
    return Coupon.objects.create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        restaurant_id=restaurant_id,
        expires_at=expires_at,
        issue_key=issue_key,
        benefit_snapshot=benefit_snapshot,
    )


@transaction.atomic
def add_stamp(user: User, restaurant_id: int, pin: str, idem_key: str | None = None):
    # 멱등(같은 요청 재발급 방지)
    if idem_key:
        cache_key = f"idem:stamp:{restaurant_id}:{idem_key}"
        prev = idem_get(cache_key)
        if prev:
            return prev

    # 매장 코드 검증
    if not _verify_pin(restaurant_id, pin):
        raise ValidationError("invalid merchant code")

    # 동시 요청 방지 (user-restaurant 잠금)
    lock_key = f"lock:stamp:{user.id}:{restaurant_id}"
    with redis_lock(lock_key, ttl=5):
        # 하루 2번 제한 체크 (식당별)
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        today_stamp_count = StampEvent.objects.using('cloudsql').filter(
            user=user,
            restaurant_id=restaurant_id,
            delta=+1,  # 적립만 카운트 (정정은 제외)
            created_at__gte=today_start,
            created_at__lte=today_end
        ).count()
        
        if today_stamp_count >= 2:
            raise ValidationError(
                f"하루 최대 2번까지만 스탬프를 적립할 수 있습니다. "
                f"오늘 이미 {today_stamp_count}번 적립하셨습니다."
            )
        
        wallet, _ = StampWallet.objects.using('cloudsql').get_or_create(
            user=user, restaurant_id=restaurant_id
        )

        prev_stamps = wallet.stamps
        wallet.stamps += 1
        StampEvent.objects.using('cloudsql').create(
            user=user, restaurant_id=restaurant_id, delta=+1, source="PIN"
        )
        reward_codes = []
        reward_details = []
        now_suffix = timezone.now().strftime("%Y%m%d%H%M%S%f")
        max_threshold = max(STAMP_THRESHOLDS)
        max_threshold_reached = False

        for threshold in STAMP_THRESHOLDS:
            if prev_stamps < threshold <= wallet.stamps:
                coupon_type_code = REWARD_COUPON_CODES.get(threshold)
                if not coupon_type_code:
                    raise ValidationError(f"stamp reward coupon type missing for threshold={threshold}")
                suffix = f"{restaurant_id}:{now_suffix}:T{threshold}"
                reward = _issue_reward_coupon(
                    user,
                    restaurant_id,
                    coupon_type_code=coupon_type_code,
                    issue_key_suffix=suffix,
                )
                logger.info(
                    "Stamp reward issued user=%s restaurant=%s threshold=%s coupon_type=%s coupon_code=%s",
                    user.id,
                    restaurant_id,
                    threshold,
                    reward.coupon_type.code,
                    reward.code,
                )
                reward_codes.append(reward.code)
                reward_details.append(
                    {
                        "threshold": threshold,
                        "coupon_code": reward.code,
                        "coupon_type": reward.coupon_type.code,
                    }
                )
                if threshold == max_threshold:
                    max_threshold_reached = True

        if max_threshold_reached:
            wallet.stamps -= max_threshold

        wallet.save()

    result = {
        "ok": True,
        "current": wallet.stamps,
        "target": STAMP_CYCLE_TARGET,
        "reward_coupon_code": reward_codes[-1] if reward_codes else None,
    }
    if reward_codes:
        result["reward_coupon_codes"] = reward_codes
        result["reward_coupons"] = reward_details
    if idem_key:
        idem_set(cache_key, result, ttl=300)
    return result



def get_all_stamp_statuses(user: User):
    restaurant_alias = router.db_for_read(AffiliateRestaurant)
    try:
        accessible_ids = list(
            AffiliateRestaurant.objects.using(restaurant_alias)
            .order_by("restaurant_id")
            .values_list("restaurant_id", flat=True)
        )
    except DatabaseError:
        accessible_ids = []

    wallet_qs = StampWallet.objects.filter(user=user)
    wallet_map = {wallet.restaurant_id: wallet for wallet in wallet_qs}

    results: list[dict] = []
    seen_ids: set[int] = set()

    for restaurant_id in accessible_ids:
        wallet = wallet_map.get(restaurant_id)
        results.append(
            {
                "restaurant_id": restaurant_id,
                "current": wallet.stamps if wallet else 0,
                "target": STAMP_CYCLE_TARGET,
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
                "target": STAMP_CYCLE_TARGET,
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
    try:
        w = StampWallet.objects.get(user=user, restaurant_id=restaurant_id)
        return {
            "current": w.stamps,
            "target": STAMP_CYCLE_TARGET,
            "updated_at": w.updated_at,
        }
    except StampWallet.DoesNotExist:
        return {"current": 0, "target": STAMP_CYCLE_TARGET, "updated_at": None}
