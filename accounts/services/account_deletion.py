import logging

from django.db import DatabaseError, connections, transaction
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.models import SocialAccount, User
from coupons.models import Coupon, InviteCode, Referral, StampEvent, StampWallet
from guests.models import GuestUser

logger = logging.getLogger(__name__)


def _resolve_coupon_db_alias() -> str:
    # 운영에서는 cloudsql, 로컬/테스트에서는 default만 있는 경우가 있다.
    if "cloudsql" in connections.databases:
        return "cloudsql"
    return "default"


def _delete_external_user_rows_or_raise(model_class, user_id: int, field_name: str, db_alias: str) -> int:
    """
    꼬임 방지용(strict) 삭제:
    - 외부 DB(cloudsql 등)에서 삭제가 실패하면 계정 삭제 전체를 중단하기 위해 예외를 올린다.
    """
    queryset = model_class.objects.using(db_alias).filter(**{field_name: user_id})
    count = queryset.count()
    if count:
        queryset.delete()
    return count


def delete_user_account(user: User) -> dict:
    user_id = user.id
    coupon_db_alias = _resolve_coupon_db_alias()

    deleted_counts = {
        "coupons": 0,
        "stamp_wallets": 0,
        "stamp_events": 0,
        "invite_codes": 0,
        "referrals_made": 0,
        "referrals_received": 0,
        "guest_unlinked": 0,
        "social_accounts": 0,
        "blacklisted_tokens": 0,
        "outstanding_tokens": 0,
    }

    # 1) 외부 DB(쿠폰/스탬프 등)부터 strict 삭제: 실패하면 계정 삭제 전체를 중단
    try:
        deleted_counts["coupons"] = _delete_external_user_rows_or_raise(Coupon, user_id, "user_id", coupon_db_alias)
        deleted_counts["stamp_wallets"] = _delete_external_user_rows_or_raise(StampWallet, user_id, "user_id", coupon_db_alias)
        deleted_counts["stamp_events"] = _delete_external_user_rows_or_raise(StampEvent, user_id, "user_id", coupon_db_alias)
        deleted_counts["invite_codes"] = _delete_external_user_rows_or_raise(InviteCode, user_id, "user_id", coupon_db_alias)
        deleted_counts["referrals_made"] = _delete_external_user_rows_or_raise(Referral, user_id, "referrer_id", coupon_db_alias)
        deleted_counts["referrals_received"] = _delete_external_user_rows_or_raise(Referral, user_id, "referee_id", coupon_db_alias)
    except Exception as exc:
        logger.error(
            "external deletion failed; aborting account deletion for user_id=%s (db=%s): %s",
            user_id,
            coupon_db_alias,
            exc,
            exc_info=True,
        )
        raise

    # 2) default DB 내 정리 작업은 트랜잭션으로 묶어서 부분 완료를 줄인다.
    with transaction.atomic(using="default"):
        deleted_counts["guest_unlinked"] = GuestUser.objects.filter(linked_user_id=user_id).update(linked_user=None)

        deleted_counts["social_accounts"] = SocialAccount.objects.filter(user_id=user_id).count()
        SocialAccount.objects.filter(user_id=user_id).delete()

        # 토큰 테이블이 있으면 반드시 정리 (꼬임 방지)
        deleted_counts["blacklisted_tokens"] = BlacklistedToken.objects.filter(token__user_id=user_id).delete()[0]
        deleted_counts["outstanding_tokens"] = OutstandingToken.objects.filter(user_id=user_id).delete()[0]

        # cross-db CASCADE로 인한 오류를 피하기 위해 계정 레코드는 SQL로 직접 삭제한다.
        with connections["default"].cursor() as cursor:
            cursor.execute("DELETE FROM accounts_user WHERE id = %s", [user_id])
            deleted_row_count = cursor.rowcount

        if deleted_row_count != 1:
            raise ValueError(f"failed to delete user row for user_id={user_id}")

    return deleted_counts
