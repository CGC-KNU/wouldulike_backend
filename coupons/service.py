from datetime import timedelta, date
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import Campaign, CouponType, Coupon, InviteCode, Referral
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
def redeem_coupon(user: User, coupon_code: str, restaurant_id=None):
    coupon = Coupon.objects.select_for_update().get(code=coupon_code, user=user)
    if coupon.status != "ISSUED":
        raise ValidationError("already used or invalid state")
    if coupon.expires_at <= timezone.now():
        raise ValidationError("expired")

    lock_key = f"lock:coupon:{coupon.id}"
    with redis_lock(lock_key, ttl=5):
        coupon.refresh_from_db()
        if coupon.status != "ISSUED":
            raise ValidationError("already used")

        coupon.status = "REDEEMED"
        coupon.redeemed_at = timezone.now()
        coupon.restaurant_id = restaurant_id
        coupon.save()
    return coupon


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
