from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Coupon
from ..service import (
    issue_signup_coupon,
    redeem_coupon,
    ensure_invite_code,
    accept_referral,
    qualify_referral_and_grant,
    claim_flash_drop,
)
from .serializers import CouponSerializer, InviteCodeSerializer


class MyCouponsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CouponSerializer

    def get_queryset(self):
        qs = Coupon.objects.filter(user=self.request.user).order_by("-issued_at")
        status_q = self.request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)
        return qs


class SignupCompleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 멱등성: issue_key Unique로 보장 → create 충돌 시 OK 응답
        try:
            c = issue_signup_coupon(request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=200)
        return Response({"coupon_code": c.code}, status=201)


class RedeemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get("coupon_code")
        restaurant_id = request.data.get("restaurant_id")
        c = redeem_coupon(request.user, code, restaurant_id)
        return Response({"ok": True, "coupon_code": c.code})


class MyInviteCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ic = ensure_invite_code(request.user)
        return Response(InviteCodeSerializer(ic).data)


class AcceptReferralView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ref = request.data.get("ref_code")
        accept_referral(request.user, ref)
        # 보상 시점: 즉시가 아니라 '가입 완성' or '첫 주문' 등에 맞춰 qualify 호출
        return Response({"ok": True})


class QualifyReferralView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # 예: 가입 플로우 마지막 단계에서 호출
        ref = qualify_referral_and_grant(request.user)
        return Response({"ok": True, "status": ref.status if ref else "NONE"})


class FlashClaimView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        idem_key = request.headers.get("Idempotency-Key") or request.data.get("idem_key")
        if not idem_key:
            return Response({"detail": "Idempotency-Key required"}, status=400)
        code = claim_flash_drop(
            request.user, campaign_code="FLASH_8PM", idem_key=idem_key
        )
        return Response({"coupon_code": code}, status=201)
