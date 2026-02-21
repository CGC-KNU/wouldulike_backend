from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import logging
import time

from ..models import Coupon
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
    check_and_expire_coupon,
    claim_final_exam_coupon,
    issue_app_open_coupon,
)
from .serializers import CouponSerializer, InviteCodeSerializer


logger = logging.getLogger(__name__)


class MyCouponsView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        user = self.request.user
        request_id = getattr(self.request, "_request_id", "n/a")
        logger.info("[req:%s] MyCouponsView.get_queryset start user=%s", request_id, getattr(user, "id", None))

        # 앱 접속(쿠폰 목록 진입) 시 앱 접속 쿠폰 발급 시도
        if getattr(user, "is_authenticated", False):
            issue_started_at = time.perf_counter()
            try:
                coupons = issue_app_open_coupon(user)
                if coupons:
                    codes = [c.code for c in coupons]
                    logger.info(
                        "app-open coupons ensured on my coupons list "
                        "(user=%s, codes=%s)",
                        user.id,
                        codes,
                    )
                else:
                    logger.info(
                        "no app-open coupon issued on my coupons list "
                        "(user=%s, reason=already_issued_or_campaign_inactive_or_out_of_period)",
                        user.id,
                    )
            except Exception as exc:  # noqa: BLE001
                # 쿠폰 발급 실패가 내 쿠폰 목록 조회 자체를 막지 않도록 예외는 로깅만 하고 무시
                logger.warning(
                    "failed to issue app-open coupon on my coupons list for user %s: %s",
                    getattr(user, "id", None),
                    exc,
                    exc_info=True,
                )
            finally:
                elapsed_ms = int((time.perf_counter() - issue_started_at) * 1000)
                level = logging.WARNING if elapsed_ms >= 3000 else logging.INFO
                logger.log(
                    level,
                    "[req:%s] issue_app_open_coupon in MyCouponsView elapsed_ms=%s user=%s",
                    request_id,
                    elapsed_ms,
                    getattr(user, "id", None),
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


class SignupCompleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 멱등성: issue_key Unique로 보장 → create 충돌 시 OK 응답
        try:
            c = issue_signup_coupon(request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=200)
        return Response({"coupon_code": c.code}, status=201)


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
            referral = accept_referral(referee=request.user, ref_code=ref_code)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict") and exc.message_dict:
                payload = exc.message_dict
            else:
                message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                payload = {"detail": message}
            status_code = (
                status.HTTP_409_CONFLICT
                if getattr(exc, "code", "") in ("referral_already_accepted", "final_exam_already_issued", "event_referral_already_accepted")
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(payload, status=status_code)

        # 기말고사 이벤트의 경우 이미 쿠폰이 발급되었고 Referral이 QUALIFIED 상태이므로
        # qualify_referral_and_grant를 호출하지 않음 (호출해도 처리할 것이 없음)
        # 일반 추천인 코드의 경우에만 qualify_referral_and_grant 호출
        if referral.campaign_code != "FINAL_EXAM_EVENT":
            qualify_referral_and_grant(request.user)

        return Response({"ok": True, "referral_id": referral.id}, status=status.HTTP_200_OK)


class QualifyReferralView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 예: 가입 플로우 마지막 단계에서 호출
        ref = qualify_referral_and_grant(request.user)
        return Response({"ok": True, "status": ref.status if ref else "NONE"})


class FlashClaimView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key") or request.data.get("idem_key")
        if not idem_key:
            return Response({"detail": "Idempotency-Key required"}, status=400)
        code = claim_flash_drop(
            request.user, campaign_code="FLASH_8PM", idem_key=idem_key
        )
        return Response({"coupon_code": code}, status=201)


class AddStampView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        restaurant_id = request.data.get("restaurant_id")
        pin = request.data.get("pin")
        idem_key = request.headers.get("Idempotency-Key") or request.data.get("idem_key")
        if not restaurant_id or not pin:
            return Response({"detail": "restaurant_id and pin required"}, status=400)
        data = add_stamp(request.user, int(restaurant_id), pin, idem_key)
        return Response(data, status=201 if data.get("reward_coupon_code") else 200)


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
            return Response({
                "ok": True,
                "total_issued": result["total_issued"],
                "coupon_codes": [c.code for c in result["coupons"]],
            }, status=201)
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
