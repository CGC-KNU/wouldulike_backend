"""
발급된 쿠폰의 모든 컬럼(필드) 실제 내용을 확인하는 명령어.
"""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import router
from django.forms.models import model_to_dict
from rest_framework.test import APIRequestFactory

from coupons.models import Coupon, Campaign, Referral
from coupons.service import accept_referral, FULL_AFFILIATE_COUPON_CODE
from coupons.utils import format_issued_coupons
from coupons.api.serializers import CouponSerializer


class Command(BaseCommand):
    help = "발급된 쿠폰의 모든 컬럼 실제 내용을 확인합니다. (DONGARILIKE/KNULIKE 테스트 발급 후 조회)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--code",
            type=str,
            choices=["DONGARILIKE", "KNULIKE"],
            default="DONGARILIKE",
            help="쿠폰 코드 (DONGARILIKE 또는 KNULIKE)",
        )
        parser.add_argument(
            "--kakao-id",
            type=int,
            required=True,
            help="테스트용 사용자 kakao_id",
        )
        parser.add_argument(
            "--issue-first",
            action="store_true",
            help="먼저 쿠폰 발급 후 조회 (이미 발급된 사용자면 스킵)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=3,
            help="출력할 쿠폰 개수 (기본 3개)",
        )
        parser.add_argument(
            "--api-response",
            action="store_true",
            help="실제 API 전달 형식만 출력 (accept 응답 + GET /my/ 형식)",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        code = options["code"]
        kakao_id = options["kakao_id"]
        issue_first = options["issue_first"]
        limit = options["limit"]
        api_response_only = options.get("api_response", False)

        user = User.objects.filter(kakao_id=kakao_id).first()
        if not user:
            user = User.objects.create_user(kakao_id=kakao_id, type_code=None)
            self.stdout.write(f"사용자 생성: kakao_id={kakao_id}, user_id={user.id}")

        ref_code = FULL_AFFILIATE_COUPON_CODE if code == "DONGARILIKE" else "KNULIKE"
        campaign_code = "FULL_AFFILIATE_EVENT" if code == "DONGARILIKE" else "KNULIKE_EVENT"

        if issue_first:
            try:
                _, issued = accept_referral(referee=user, ref_code=ref_code)
                self.stdout.write(
                    self.style.SUCCESS(f"쿠폰 발급 완료: {len(issued)}개")
                )
            except Exception as e:
                if "이미" in str(e):
                    self.stdout.write(self.style.WARNING(f"이미 발급됨: {e}"))
                else:
                    raise

        alias = router.db_for_read(Coupon)
        try:
            campaign = Campaign.objects.using(alias).get(code=campaign_code, active=True)
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"캠페인 {campaign_code}을 찾을 수 없습니다."))
            return

        coupons = list(
            Coupon.objects.using(alias)
            .filter(user=user, campaign=campaign)
            .select_related("coupon_type", "campaign")
            .order_by("id")[:limit]
        )

        if not coupons:
            self.stdout.write(
                self.style.WARNING(
                    f"해당 사용자의 {campaign_code} 쿠폰이 없습니다. "
                    "--issue-first 옵션으로 먼저 발급하세요."
                )
            )
            return

        if api_response_only:
            self._show_api_response(user, coupons, campaign_code, ref_code, issue_first)
            return

        self.stdout.write(f"\n=== 쿠폰 전체 컬럼 (총 {len(coupons)}개 중 {limit}개) ===\n")

        for idx, coupon in enumerate(coupons, 1):
            # model_to_dict: FK는 ID만, DateTime은 그대로
            data = model_to_dict(
                coupon,
                fields=[
                    "code",
                    "user",
                    "coupon_type",
                    "campaign",
                    "status",
                    "issued_at",
                    "expires_at",
                    "redeemed_at",
                    "restaurant_id",
                    "benefit_snapshot",
                    "issue_key",
                ],
            )
            # FK 객체 → 코드/이름으로 보기 쉽게
            data["user_id"] = coupon.user_id
            data["coupon_type_id"] = coupon.coupon_type_id
            data["coupon_type_code"] = coupon.coupon_type.code if coupon.coupon_type else None
            data["coupon_type_title"] = coupon.coupon_type.title if coupon.coupon_type else None
            data["campaign_id"] = coupon.campaign_id
            data["campaign_code"] = coupon.campaign.code if coupon.campaign else None

            self.stdout.write(f"--- [{idx}] code={coupon.code} ---")
            self.stdout.write(
                json.dumps(data, indent=2, ensure_ascii=False, default=str)
            )
            self.stdout.write("")

    def _show_api_response(self, user, coupons, campaign_code, ref_code, was_issued):
        """실제 API 전달 형식 출력."""
        ref_alias = router.db_for_read(Referral)
        referral = (
            Referral.objects.using(ref_alias)
            .filter(referee=user, campaign_code=campaign_code)
            .order_by("-id")
            .first()
        )
        referral_id = referral.id if referral else None

        # 1) POST /api/coupons/referrals/accept/ 응답 (발급 시 전달되는 내용)
        issued_formatted = format_issued_coupons(coupons)
        accept_payload = {
            "ok": True,
            "referral_id": referral_id,
            "issued_coupons": issued_formatted,
        }
        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write("1. POST /api/coupons/referrals/accept/ 응답 (발급 직후 전달)")
        self.stdout.write("   요청: { \"ref_code\": \"" + ref_code + "\" }")
        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write(json.dumps(accept_payload, indent=2, ensure_ascii=False, default=str))
        self.stdout.write("")

        # 2) GET /api/coupons/my/ 응답 (쿠폰 목록 조회 시 전달 - CouponSerializer)
        factory = APIRequestFactory()
        request = factory.get("/api/coupons/my/")
        request.user = user
        serializer = CouponSerializer(coupons, many=True, context={"request": request})
        my_coupons_data = serializer.data

        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write("2. GET /api/coupons/my/ 응답 (쿠폰 목록 - 위 쿠폰들)")
        self.stdout.write("   results 배열 중 해당 쿠폰들:")
        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write(json.dumps(my_coupons_data, indent=2, ensure_ascii=False, default=str))
