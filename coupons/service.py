from datetime import date, datetime
from django.db import transaction, IntegrityError, router
from utils.db_locks import locked_get
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import (
    Campaign,
    CouponType,
    Coupon,
    InviteCode,
    Referral,
    MerchantPin,
    StampWallet,
    StampEvent,
)
from .utils import make_coupon_code, redis_lock, idem_get, idem_set


User = get_user_model()


GLOBAL_COUPON_EXPIRY = datetime(2026, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
REFERRAL_MAX_REWARDS_PER_REFERRER = 5

def _expires_at(ct: CouponType):
    return GLOBAL_COUPON_EXPIRY


def ensure_invite_code(user: User) -> InviteCode:
    if hasattr(user, "invite_code"):
        return user.invite_code
    # 간단 충돌 회피
    for _ in range(5):
        code = make_coupon_code()[:8].upper()
        if not InviteCode.objects.filter(code=code).exists():
            return InviteCode.objects.create(user=user, code=code)
    raise RuntimeError("invite code collision")


def issue_signup_coupon(user: User):
    ct = CouponType.objects.get(code="WELCOME_3000")
    camp = Campaign.objects.get(code="SIGNUP_WELCOME", active=True)
    issue_key = f"SIGNUP:{user.id}"
    return Coupon.objects.create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        expires_at=_expires_at(ct),
        issue_key=issue_key,
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

    return {
        "code": coupon.code,
        "status": coupon.status,
        "expires_at": coupon.expires_at,
        "redeemed_at": coupon.redeemed_at,
        "campaign": coupon.campaign_id,
        "coupon_type": coupon.coupon_type_id,
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

            Coupon.objects.using(db_alias).create(

                code=make_coupon_code(),

                user=ref.referrer,

                coupon_type=ref_ct,

                campaign=ref_camp,

                expires_at=_expires_at(ref_ct),

                issue_key=f"REFERRAL_REFERRER:{ref.referrer_id}:{referee.id}",

            )

        new_ct = CouponType.objects.using(db_alias).get(code="REFERRAL_BONUS_REFEREE")

        Coupon.objects.using(db_alias).create(

            code=make_coupon_code(),

            user=referee,

            coupon_type=new_ct,

            campaign=ref_camp,

            expires_at=_expires_at(new_ct),

            issue_key=f"REFERRAL_REFEREE:{referee.id}",

        )

        return ref



def claim_flash_drop(user: User, campaign_code: str, idem_key: str):
    cache_key = f"idem:{idem_key}"
    prev = idem_get(cache_key)
    if prev:
        return prev

    camp = Campaign.objects.get(code=campaign_code, active=True)
    quota_key = f"quota:{camp.id}:{date.today():%Y%m%d}"
    cli = __import__("django_redis").get_redis_connection()

    with redis_lock(f"lock:flash:{camp.id}", ttl=3):
        remaining = cli.decr(quota_key)
        if remaining < 0:
            cli.incr(quota_key)  # 복원
            raise ValidationError("sold out")

        ct = CouponType.objects.get(code="FLASH_3000")
        coupon = Coupon.objects.create(
            code=make_coupon_code(),
            user=user,
            coupon_type=ct,
            campaign=camp,
            expires_at=_expires_at(ct),
            issue_key=f"FLASH:{camp.id}:{user.id}:{date.today():%Y%m%d}",
        )
    idem_set(cache_key, coupon.code, ttl=300)
    return coupon.code


# ---- Stamp (Punch) Card Service ----

# 목표 개수 및 보상 정의 (시드로 생성 필요)
STAMP_THRESHOLDS = (5, 10)
STAMP_CYCLE_TARGET = max(STAMP_THRESHOLDS)
REWARD_COUPON_CODE = "STAMP_REWARD_8"
REWARD_CAMPAIGN_CODE = "STAMP_REWARD"


def _verify_pin(restaurant_id: int, pin: str) -> bool:
    try:
        mp = MerchantPin.objects.get(restaurant_id=restaurant_id)
    except MerchantPin.DoesNotExist:
        return False

    if mp.algo == "STATIC":
        return pin == mp.secret
    # For TOTP, integrate pyotp in actual deployment.
    # import pyotp
    # return pyotp.TOTP(mp.secret, interval=mp.period_sec).verify(pin)
    return False


def _issue_reward_coupon(user: User, restaurant_id: int, issue_key_suffix: str):
    ct = CouponType.objects.get(code=REWARD_COUPON_CODE)
    camp = Campaign.objects.get(code=REWARD_CAMPAIGN_CODE, active=True)
    issue_key = f"STAMP_REWARD:{user.id}:{issue_key_suffix}"
    expires_at = _expires_at(ct)
    return Coupon.objects.create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        restaurant_id=restaurant_id,
        expires_at=expires_at,
        issue_key=issue_key,
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
        now_suffix = timezone.now().strftime("%Y%m%d%H%M%S%f")
        max_threshold = max(STAMP_THRESHOLDS)
        max_threshold_reached = False

        for threshold in STAMP_THRESHOLDS:
            if prev_stamps < threshold <= wallet.stamps:
                suffix = f"{restaurant_id}:{now_suffix}:T{threshold}"
                reward = _issue_reward_coupon(user, restaurant_id, issue_key_suffix=suffix)
                reward_codes.append(reward.code)
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
    if idem_key:
        idem_set(cache_key, result, ttl=300)
    return result



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
