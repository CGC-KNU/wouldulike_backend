import os
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from ..models import Coupon
from ..utils import format_issued_coupons
from ..service import (
    issue_signup_coupon,
    redeem_coupon,
    ensure_invite_code,
    accept_referral,
    qualify_referral_and_grant,
    claim_flash_drop,
    add_stamp,
    get_all_stamp_statuses,
    get_stamp_status,
    STAMP_DAILY_EARN_LIMIT,
    check_and_expire_coupon,
    claim_final_exam_coupon,
    issue_app_open_coupon,
    delete_expired_coupons_for_user,
)
from .serializers import CouponSerializer, InviteCodeSerializer


logger = logging.getLogger(__name__)

# 쿠폰 목록 진입 시 앱 접속 쿠폰 발급 여부 (0: 비활성화)
AUTH_ISSUE_APP_OPEN_COUPON_ON_COUPON_LIST = (
    os.getenv("AUTH_ISSUE_APP_OPEN_COUPON_ON_COUPON_LIST", "1") in ("1", "true", "True")
)


class MyCouponsView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        user = self.request.user
        request_id = getattr(self.request, "_request_id", "n/a")
        logger.info("[req:%s] MyCouponsView.get_queryset start user=%s", request_id, getattr(user, "id", None))

        # 쿠폰함 조회 시 사용자의 만료 쿠폰 자동 정리
        try:
            deleted_count = delete_expired_coupons_for_user(user)
            if deleted_count:
                logger.info(
                    "[req:%s] auto-deleted expired coupons user=%s deleted=%s",
                    request_id,
                    getattr(user, "id", None),
                    deleted_count,
                )
        except Exception:
            logger.warning(
                "[req:%s] failed to auto-delete expired coupons user=%s",
                request_id,
                getattr(user, "id", None),
                exc_info=True,
            )

        # 앱 접속(쿠폰 목록 진입) 시 앱 접속 쿠폰 발급 시도
        # 신규가입 직후(1시간 이내)에는 스킵 - 이미 신규가입 쿠폰 1개만 발급됨
        self._issued_app_open_coupons = []
        created_at = getattr(user, "created_at", None)
        is_new_user = created_at and (timezone.now() - created_at) < timedelta(hours=1)
        should_issue_app_open = (
            getattr(user, "is_authenticated", False)
            and AUTH_ISSUE_APP_OPEN_COUPON_ON_COUPON_LIST
            and not is_new_user
        )
        if should_issue_app_open:
            try:
                coupons = issue_app_open_coupon(user)
                if coupons:
                    self._issued_app_open_coupons = coupons
                    codes = [c.code for c in coupons]
                    logger.info(
                        "app-open coupons ensured on my coupons list (user=%s, codes=%s)",
                        user.id,
                        codes,
                    )
                else:
                    logger.info(
                        "no app-open coupon issued on my coupons list (user=%s, reason=already_issued_or_campaign_inactive_or_out_of_period)",
                        user.id,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "failed to issue app-open coupon on my coupons list for user %s: %s",
                    getattr(user, "id", None),
                    exc,
                    exc_info=True,
                )

        qs = (
            Coupon.objects.select_related("coupon_type", "campaign")
            .filter(user=user)
            .order_by("-issued_at")
        )
        status_q = self.request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)
        logger.info("[req:%s] MyCouponsView.get_queryset end user=%s", request_id, getattr(user, "id", None))
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        issued = getattr(self, "_issued_app_open_coupons", [])
        if issued:
            # ListAPIView: response.data는 페이징 없으면 list, 있으면 dict
            if isinstance(response.data, list):
                response.data = {"results": response.data, "issued_coupons": format_issued_coupons(issued)}
            else:
                response.data["issued_coupons"] = format_issued_coupons(issued)
        return response


class SignupCompleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 멱등성: issue_key Unique로 보장 → create 충돌 시 OK 응답
        try:
            issued = issue_signup_coupon(request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=200)
        payload = {
            "coupon_code": issued[0].code if issued else None,
            "issued_coupons": format_issued_coupons(issued),
        }
        return Response(payload, status=201)


class RedeemView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("coupon_code")
        restaurant_id = request.data.get("restaurant_id")
        pin = request.data.get("pin") or request.data.get("pin_code")
        if not code or not restaurant_id or not pin:
            return Response({"detail": "coupon_code, restaurant_id and pin required"}, status=400)
        try:
            restaurant_id_int = int(restaurant_id)
        except (TypeError, ValueError):
            return Response({"detail": "restaurant_id must be numeric"}, status=400)

        try:
            c = redeem_coupon(request.user, code, restaurant_id_int, pin)
            return Response({"ok": True, "coupon_code": c.code})
        except Coupon.DoesNotExist:
            return Response({"detail": "not found"}, status=404)
        except DjangoValidationError as e:
            msg = str(e)
            if "invalid merchant" in msg:
                return Response({"detail": msg}, status=403)
            if "expired" in msg:
                return Response({"detail": msg}, status=410)
            if "already used" in msg:
                return Response({"detail": msg}, status=409)
            return Response({"detail": msg}, status=400)
        except Exception as e:
            if request.query_params.get("_diag") == "1":
                import traceback
                return Response({"detail": "internal error", "error": str(e), "trace": traceback.format_exc().splitlines()[-5:]}, status=500)
            return Response({"detail": "internal error"}, status=500)


class CheckCouponView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("coupon_code")
        if not code:
            return Response({"detail": "coupon_code required"}, status=400)
        try:
            data = check_and_expire_coupon(request.user, code)
            return Response(data)
        except Coupon.DoesNotExist:
            return Response({"detail": "not found"}, status=404)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=400)
        except Exception as e:
            if request.query_params.get("_diag") == "1":
                import traceback
                return Response({"detail": "internal error", "error": str(e), "trace": traceback.format_exc().splitlines()[-5:]}, status=500)
            return Response({"detail": "internal error"}, status=500)


class MyInviteCodeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ic = ensure_invite_code(request.user)
        return Response(InviteCodeSerializer(ic).data)


class AcceptReferralView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ref_code = request.data.get("ref_code")
        if not ref_code:
            raise DRFValidationError({"ref_code": "필수 필드입니다."})

        try:
            referral, ref_issued = accept_referral(referee=request.user, ref_code=ref_code)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict") and exc.message_dict:
                payload = exc.message_dict
            else:
                message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                payload = {"detail": message}
            status_code = (
                status.HTTP_409_CONFLICT
                if getattr(exc, "code", "") in (
                    "referral_already_accepted",
                    "final_exam_already_issued",
                    "event_referral_already_accepted",
                    "new_semester_already_issued",
                    "knulike_already_issued",
                    "datelike_already_issued",
                    "full_affiliate_already_issued",
                    "booth_visit_already_issued",
                )
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(payload, status=status_code)

        # 기말고사/신학기 이벤트의 경우 이미 쿠폰이 발급되었고 Referral이 QUALIFIED 상태이므로
        # qualify_referral_and_grant를 호출하지 않음 (호출해도 처리할 것이 없음)
        # 일반 추천인 코드의 경우에만 qualify_referral_and_grant 호출
        qual_issued = []
        if referral.campaign_code not in (
            "FINAL_EXAM_EVENT",
            "NEW_SEMESTER_EVENT",
            "KNULIKE_EVENT",
            "FULL_AFFILIATE_EVENT",
            "BOOTH_VISIT_EVENT",
        ):
            _, qual_issued = qualify_referral_and_grant(request.user)

        issued_coupons = format_issued_coupons(ref_issued + qual_issued)
        payload = {"ok": True, "referral_id": referral.id}
        if issued_coupons:
            payload["issued_coupons"] = issued_coupons
        return Response(payload, status=status.HTTP_200_OK)


class QualifyReferralView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 예: 가입 플로우 마지막 단계에서 호출
        ref, issued = qualify_referral_and_grant(request.user)
        payload = {"ok": True, "status": ref.status if ref else "NONE"}
        if issued:
            payload["issued_coupons"] = format_issued_coupons(issued)
        return Response(payload)


class FlashClaimView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key") or request.data.get("idem_key")
        if not idem_key:
            return Response({"detail": "Idempotency-Key required"}, status=400)
        coupon = claim_flash_drop(
            request.user, campaign_code="FLASH_8PM", idem_key=idem_key
        )
        payload = {"coupon_code": coupon.code, "issued_coupons": format_issued_coupons([coupon])}
        return Response(payload, status=201)


class AddStampView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        restaurant_id = request.data.get("restaurant_id")
        pin = request.data.get("pin")
        count = request.data.get("count", 1)
        idem_key = request.headers.get("Idempotency-Key") or request.data.get("idem_key")
        if not restaurant_id or not pin:
            return Response({"detail": "restaurant_id and pin required"}, status=400)
        try:
            restaurant_id_int = int(restaurant_id)
        except (TypeError, ValueError):
            return Response({"detail": "restaurant_id must be numeric"}, status=400)
        try:
            stamp_count = int(count)
        except (TypeError, ValueError):
            return Response({"detail": "count must be numeric (1~4)"}, status=400)

        try:
            data = add_stamp(
                request.user,
                restaurant_id_int,
                pin,
                idem_key=idem_key,
                count=stamp_count,
            )
            return Response(data, status=201 if data.get("reward_coupon_code") else 200)
        except DjangoValidationError as e:
            if hasattr(e, "messages") and e.messages:
                msg = e.messages[0]
            else:
                msg = str(e)
            code = getattr(e, "code", "")
            # PIN 불일치
            if "invalid merchant code" in msg:
                return Response(
                    {
                        "detail": "PIN 번호가 올바르지 않아요. 다시 확인해 주세요.",
                        "code": "invalid_pin",
                    },
                    status=403,
                )
            # 일일 적립 제한 초과
            if code == "stamp_daily_limit_reached" or "daily stamp limit reached" in msg:
                return Response(
                    {
                        "detail": f"이 식당은 하루 최대 {STAMP_DAILY_EARN_LIMIT}회까지 스탬프를 적립할 수 있어요.",
                        "code": "stamp_daily_limit_reached",
                    },
                    status=429,
                )
            if code == "invalid_stamp_count" or "stamp count must be between 1 and 4" in msg:
                return Response(
                    {
                        "detail": "스탬프 적립 개수는 1개 이상 4개 이하만 가능해요.",
                        "code": "invalid_stamp_count",
                    },
                    status=400,
                )
            return Response(
                {
                    "detail": "스탬프 적립에 실패했어요. 잠시 후 다시 시도해 주세요.",
                    "code": "stamp_add_failed",
                },
                status=400,
            )
        except Exception:
            logger.exception(
                "unexpected error in AddStampView (user=%s, restaurant_id=%s)",
                getattr(request.user, "id", None),
                restaurant_id,
            )
            return Response({"detail": "internal error"}, status=500)


class MyStampStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        restaurant_id = request.query_params.get("restaurant_id")
        if not restaurant_id:
            return Response({"detail": "restaurant_id required"}, status=400)
        data = get_stamp_status(request.user, int(restaurant_id))
        return Response(data)


class MyAllStampStatusView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = get_all_stamp_statuses(request.user)
        return Response({"results": data})


class ClaimFinalExamCouponView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        coupon_code = request.data.get("coupon_code")
        if not coupon_code:
            return Response({"detail": "coupon_code required"}, status=400)
        
        try:
            result = claim_final_exam_coupon(request.user, coupon_code)
            payload = {
                "ok": True,
                "total_issued": result["total_issued"],
                "coupon_codes": [c.code for c in result["coupons"]],
                "issued_coupons": format_issued_coupons(result["coupons"]),
            }
            return Response(payload, status=201)
        except DjangoValidationError as e:
            msg = str(e)
            if "invalid coupon code" in msg.lower():
                return Response({"detail": "유효하지 않은 쿠폰 코드입니다."}, status=400)
            if "이미 발급받은" in msg or "already" in msg.lower():
                return Response({"detail": msg}, status=409)
            return Response({"detail": msg}, status=400)
        except Exception as e:
            if request.query_params.get("_diag") == "1":
                import traceback
                return Response({"detail": "internal error", "error": str(e), "trace": traceback.format_exc().splitlines()[-5:]}, status=500)
            return Response({"detail": "internal error"}, status=500)
