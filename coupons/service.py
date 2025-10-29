import uuid
import random
import logging
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


GLOBAL_COUPON_EXPIRY = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
REFERRAL_MAX_REWARDS_PER_REFERRER = 5


MAX_COUPONS_PER_RESTAURANT = 200

COUPON_TYPE_EXCLUDED_RESTAURANTS: dict[str, set[int]] = {
    "WELCOME_3000": {30},
    "REFERRAL_BONUS_REFERRER": {30},
    "REFERRAL_BONUS_REFEREE": {30},
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
    if hasattr(user, "invite_code"):
        return user.invite_code

    max_attempts = 32
    for attempt in range(max_attempts):
        length = 12 if attempt >= 8 else 8
        code = make_coupon_code(length).upper()
        if InviteCode.objects.filter(code=code).exists():
            continue
        try:
            return InviteCode.objects.create(user=user, code=code)
        except IntegrityError:
            continue

    fallback_code = f"INV{user.id:06d}{uuid.uuid4().hex[:4].upper()}"
    invite, _ = InviteCode.objects.update_or_create(
        user=user,
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

            if locked_qs.filter(referee=referee).exists():

                raise ValidationError(

                    "이미 추천을 수락했습니다.",

                    code="referral_already_accepted",

                )

            active_referrals = (
                locked_qs.filter(referrer=referrer)
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

        try:

            ref = locked_qs.get(referee=referee)

        except Referral.DoesNotExist:

            return None

        if ref.status != "PENDING":

            return ref

        current_reward_count = (
            locked_qs.filter(referrer=ref.referrer, status="QUALIFIED")
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
        return ref



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
        wallet, _ = StampWallet.objects.get_or_create(
            user=user, restaurant_id=restaurant_id
        )

        prev_stamps = wallet.stamps
        wallet.stamps += 1
        StampEvent.objects.create(
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
