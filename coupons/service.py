from datetime import timedelta, date
from django.db import transaction
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


def _expires_at(ct: CouponType):
    return timezone.now() + timedelta(days=ct.valid_days)


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
    # Lock coupon row first and handle expiry eagerly
    coupon = Coupon.objects.select_for_update().get(code=coupon_code, user=user)
    if coupon.status != "ISSUED":
        raise ValidationError("already used or invalid state")

    now = timezone.now()
    if coupon.expires_at <= now:
        # Mark as expired on-the-fly
        coupon.status = "EXPIRED"
        coupon.save(update_fields=["status"])
        raise ValidationError("expired")

    # Verify merchant PIN after confirming coupon is still valid
    if not _verify_pin(restaurant_id, pin):
        raise ValidationError("invalid merchant code")

    lock_key = f"lock:coupon:{coupon.id}"
    with redis_lock(lock_key, ttl=5):
        coupon.refresh_from_db()
        if coupon.status != "ISSUED":
            raise ValidationError("already used")
        if coupon.expires_at <= timezone.now():
            coupon.status = "EXPIRED"
            coupon.save(update_fields=["status"])
            raise ValidationError("expired")

        coupon.status = "REDEEMED"
        coupon.redeemed_at = timezone.now()
        coupon.restaurant_id = restaurant_id
        coupon.save()
    return coupon


@transaction.atomic
def check_and_expire_coupon(user: User, coupon_code: str) -> dict:
    """Check coupon validity; if expired, mark EXPIRED and return status.

    Returns a minimal status payload for the client to decide UI flow.
    """
    coupon = Coupon.objects.select_for_update().get(code=coupon_code, user=user)
    now = timezone.now()
    if coupon.status == "ISSUED" and coupon.expires_at <= now:
        coupon.status = "EXPIRED"
        coupon.save(update_fields=["status"])

    return {
        "code": coupon.code,
        "status": coupon.status,
        "expires_at": coupon.expires_at,
        "redeemed_at": coupon.redeemed_at,
        "campaign": coupon.campaign_id,
        "coupon_type": coupon.coupon_type_id,
    }


def accept_referral(referee: User, ref_code: str):
    try:
        referrer = InviteCode.objects.select_related("user").get(code=ref_code).user
    except InviteCode.DoesNotExist:
        raise ValidationError("invalid referral code")
    if referrer.id == referee.id:
        raise ValidationError("self referral not allowed")

    # 단순 어뷰즈 룰(동일 디바이스/번호 체크는 별도 계층에서)
    Referral.objects.create(referrer=referrer, referee=referee, code_used=ref_code)


@transaction.atomic
def qualify_referral_and_grant(referee: User):
    # referee 가입 완료 시점 등에서 호출
    try:
        ref = Referral.objects.select_for_update().get(referee=referee)
    except Referral.DoesNotExist:
        return None

    if ref.status != "PENDING":
        return ref

    ref.status = "QUALIFIED"
    ref.qualified_at = timezone.now()
    ref.save()

    # 보상 발급
    ref_ct = CouponType.objects.get(code="REFERRAL_BONUS_REFERRER")
    ref_camp = Campaign.objects.get(code="REFERRAL", active=True)
    Coupon.objects.create(
        code=make_coupon_code(),
        user=ref.referrer,
        coupon_type=ref_ct,
        campaign=ref_camp,
        expires_at=_expires_at(ref_ct),
        issue_key=f"REFERRAL_REFERRER:{ref.referrer_id}:{referee.id}",
    )

    new_ct = CouponType.objects.get(code="REFERRAL_BONUS_REFEREE")
    Coupon.objects.create(
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
STAMP_TARGET = 8
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


def _issue_reward_coupon(user: User, issue_key_suffix: str):
    ct = CouponType.objects.get(code=REWARD_COUPON_CODE)
    camp = Campaign.objects.get(code=REWARD_CAMPAIGN_CODE, active=True)
    issue_key = f"STAMP_REWARD:{user.id}:{issue_key_suffix}"
    expires_at = timezone.now() + timezone.timedelta(days=ct.valid_days)
    return Coupon.objects.create(
        code=make_coupon_code(),
        user=user,
        coupon_type=ct,
        campaign=camp,
        expires_at=expires_at,
        issue_key=issue_key,
    )


@transaction.atomic
def add_stamp(user: User, restaurant_id: int, pin: str, idem_key: str | None = None):
    # 멱등성(같은 요청 재시도 방지)
    if idem_key:
        cache_key = f"idem:stamp:{restaurant_id}:{idem_key}"
        prev = idem_get(cache_key)
        if prev:
            return prev

    # 매장 코드 검증
    if not _verify_pin(restaurant_id, pin):
        raise ValidationError("invalid merchant code")

    # 동시 적립 방지 락 (user-restaurant 별)
    lock_key = f"lock:stamp:{user.id}:{restaurant_id}"
    with redis_lock(lock_key, ttl=5):
        # 상태 잠금
        wallet, _ = (
            StampWallet.objects.select_for_update().get_or_create(
                user=user, restaurant_id=restaurant_id
            )
        )

        # 적립
        wallet.stamps += 1
        StampEvent.objects.create(
            user=user, restaurant_id=restaurant_id, delta=+1, source="PIN"
        )
        reward_issued = None

        # 보상 조건 달성
        if wallet.stamps >= STAMP_TARGET:
            # 보상 쿠폰 발급
            reward_issued = _issue_reward_coupon(
                user, issue_key_suffix=f"{restaurant_id}:{timezone.now().date():%Y%m%d}"
            )
            # 정책 1: 리셋(0으로)
            wallet.stamps = 0
            # 정책 2(이월): wallet.stamps -= STAMP_TARGET

        wallet.save()

    result = {
        "ok": True,
        "current": wallet.stamps,
        "target": STAMP_TARGET,
        "reward_coupon_code": reward_issued.code if reward_issued else None,
    }
    if idem_key:
        idem_set(cache_key, result, ttl=300)
    return result


def get_stamp_status(user: User, restaurant_id: int):
    try:
        w = StampWallet.objects.get(user=user, restaurant_id=restaurant_id)
        return {
            "current": w.stamps,
            "target": STAMP_TARGET,
            "updated_at": w.updated_at,
        }
    except StampWallet.DoesNotExist:
        return {"current": 0, "target": STAMP_TARGET, "updated_at": None}
