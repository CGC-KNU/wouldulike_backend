from django.db.models import Count
from django.utils import timezone
from django.contrib.auth import authenticate as django_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
import logging

from coupons.models import MerchantPin, Coupon, StampEvent
from django.db.models import Q
from restaurants.models import AffiliateRestaurant
from accounts.models import User
from .models import OwnerProfile, AdminConfig

logger = logging.getLogger(__name__)


class OwnerRestaurantListView(APIView):
    """
    식당 목록
    - 관리자(is_admin): 전체 제휴 식당
    - 점주: MerchantPin이 등록된 식당만
    GET /api/dashboard/restaurants/?search=<query>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        is_admin = bool(request.auth.get("is_admin", False))

        if is_admin:
            qs = AffiliateRestaurant.objects.filter(is_affiliate=True).order_by("name")
            if search:
                qs = qs.filter(name__icontains=search)
            restaurant_list = list(qs[:100])
            # 각 식당의 tier 조회 (OwnerProfile 없으면 None)
            owner_map = {
                op.restaurant_id: op.tier
                for op in OwnerProfile.objects.filter(
                    restaurant_id__in=[r.restaurant_id for r in restaurant_list]
                )
            }
            restaurants = [
                {
                    "restaurant_id": r.restaurant_id,
                    "name": r.name,
                    "tier": owner_map.get(r.restaurant_id),  # None이면 미등록
                    "is_affiliate": r.is_affiliate,
                }
                for r in restaurant_list
            ]
        else:
            qs = MerchantPin.objects.select_related("restaurant").filter(
                restaurant__isnull=False
            )
            if search:
                qs = qs.filter(restaurant__name__icontains=search)
            restaurants = [
                {"restaurant_id": p.restaurant.restaurant_id, "name": p.restaurant.name}
                for p in qs[:20]
            ]
        return Response({"restaurants": restaurants})


class VerifyOwnerView(APIView):
    """
    점주 첫 인증: PIN 검증 후 OwnerProfile 생성
    POST /api/dashboard/auth/verify-owner/
    Body: { restaurant_id, pin }
    Header: Authorization: Bearer <pending_token>
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        restaurant_id = request.data.get("restaurant_id")
        pin = request.data.get("pin")

        if not restaurant_id or not pin:
            return Response(
                {"success": False, "message": "restaurant_id와 pin이 필요합니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 이미 점주 등록된 계정이면 재인증 불필요
        try:
            owner = request.user.owner_profile
            refresh = RefreshToken.for_user(request.user)
            refresh["is_owner"] = True
            refresh["restaurant_id"] = owner.restaurant_id
            return Response({
                "success": True,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "restaurant_id": owner.restaurant_id,
                "tier": owner.tier,
            })
        except OwnerProfile.DoesNotExist:
            pass

        # PIN 검증
        try:
            merchant_pin = MerchantPin.objects.get(restaurant_id=restaurant_id)
        except MerchantPin.DoesNotExist:
            return Response(
                {"success": False, "message": "등록된 매장을 찾을 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if merchant_pin.secret != str(pin):
            return Response(
                {"success": False, "message": "PIN이 올바르지 않습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 해당 restaurant에 이미 점주 2명이 등록되어 있으면 제한
        owner_count = OwnerProfile.objects.filter(restaurant_id=restaurant_id).count()
        if owner_count >= 2:
            return Response(
                {"success": False, "message": "해당 매장에는 점주 계정이 최대 2명까지만 등록됩니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # OwnerProfile 생성
        try:
            restaurant = AffiliateRestaurant.objects.get(restaurant_id=restaurant_id)
        except AffiliateRestaurant.DoesNotExist:
            return Response(
                {"success": False, "message": "매장 정보를 찾을 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner = OwnerProfile.objects.create(
            user=request.user,
            restaurant=restaurant,
            tier="FREE",
        )

        refresh = RefreshToken.for_user(request.user)
        refresh["is_owner"] = True
        refresh["restaurant_id"] = owner.restaurant_id

        return Response({
            "success": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "restaurant_id": owner.restaurant_id,
            "tier": owner.tier,
        })


class AppTokenView(APIView):
    """
    앱 → 웹뷰 자동 로그인
    POST /api/dashboard/auth/app-token/
    Body: { token: <app_jwt> }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("token")
        if not token_str:
            return Response({"is_owner": False}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = AccessToken(token_str)
            user_id = token["user_id"]
        except TokenError:
            return Response({"is_owner": False}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = User.objects.get(pk=user_id)
            owner = user.owner_profile
        except (User.DoesNotExist, OwnerProfile.DoesNotExist):
            return Response({"is_owner": False}, status=status.HTTP_401_UNAUTHORIZED)

        if not owner.is_active:
            return Response({"is_owner": False}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        refresh["is_owner"] = True
        refresh["restaurant_id"] = owner.restaurant_id

        return Response({
            "is_owner": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "restaurant_id": owner.restaurant_id,
            "tier": owner.tier,
        })


class AdminLoginView(APIView):
    """
    환경변수 기반 관리자 로그인 (DASHBOARD_ADMIN_USERNAME / DASHBOARD_ADMIN_PASSWORD)
    POST /api/dashboard/auth/admin-login/
    Body: { username, password }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        import os
        admin_username = os.getenv("DASHBOARD_ADMIN_USERNAME", "")
        admin_password = os.getenv("DASHBOARD_ADMIN_PASSWORD", "")

        if not admin_username or not admin_password:
            logger.error("AdminLogin: DASHBOARD_ADMIN_USERNAME/PASSWORD not set")
            return Response(
                {"success": False, "message": "관리자 계정이 설정되지 않았습니다."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not username or not password:
            return Response(
                {"success": False, "message": "아이디와 비밀번호를 입력해주세요."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # DB에 저장된 비밀번호가 있으면 우선 사용, 없으면 환경변수로 폴백
        db_pw = AdminConfig.get("main_password_hash")
        if db_pw:
            valid = (username == admin_username and AdminConfig.check_password("main_password_hash", password))
        else:
            valid = (username == admin_username and password == admin_password)

        if not valid:
            logger.warning(f"AdminLogin failed for username={username!r}")
            return Response(
                {"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # JWT 발급용 더미 관리자 유저 (kakao_id=0 으로 고정)
        user, _ = User.objects.get_or_create(
            kakao_id=0,
            defaults={"username": "0", "is_staff": True, "is_superuser": True},
        )

        refresh = RefreshToken.for_user(user)
        refresh["is_owner"] = True
        refresh["is_admin"] = True

        logger.info(f"AdminLogin success for username={username!r}")
        return Response({
            "success": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class RestaurantInfoView(APIView):
    """
    점주 식당 정보 조회 및 수정
    GET  /api/dashboard/restaurant/
    PATCH /api/dashboard/restaurant/
    수정 허용 필드: description, phone_number, main_menu, url
    """
    permission_classes = [IsAuthenticated]

    EDITABLE_FIELDS = ["description", "phone_number", "main_menu", "url"]

    def _get_restaurant(self, request):
        """is_admin이면 ?restaurant_id 파라미터로, 점주면 OwnerProfile로 식당 조회."""
        is_admin = bool(request.auth.get("is_admin", False))
        if is_admin:
            rid = request.query_params.get("restaurant_id") or request.data.get("restaurant_id")
            if not rid:
                return None, Response({"detail": "restaurant_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                return AffiliateRestaurant.objects.get(restaurant_id=int(rid)), None
            except (AffiliateRestaurant.DoesNotExist, ValueError):
                return None, Response({"detail": "식당을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        else:
            try:
                return request.user.owner_profile.restaurant, None
            except OwnerProfile.DoesNotExist:
                return None, Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

    def get(self, request):
        r, err = self._get_restaurant(request)
        if err:
            return err

        return Response({
            "restaurant_id": r.restaurant_id,
            "name": r.name,
            "description": r.description or "",
            "phone_number": r.phone_number or "",
            "main_menu": r.main_menu or "",
            "url": r.url or "",
            "address": r.address or "",
            "category": r.category or "",
        })

    def patch(self, request):
        r, err = self._get_restaurant(request)
        if err:
            return err
        updated = []

        for field in self.EDITABLE_FIELDS:
            if field in request.data:
                setattr(r, field, request.data[field])
                updated.append(field)

        if not updated:
            return Response({"detail": "변경할 내용이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            r.save(update_fields=updated)
        except Exception as e:
            logger.error(f"RestaurantInfoView PATCH error: {e}")
            return Response({"detail": "저장에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "success": True,
            "updated_fields": updated,
        })


class AdminRestaurantView(APIView):
    """
    관리자 전용 식당 비활성화/삭제
    PATCH /api/dashboard/admin/restaurants/<id>/  → is_affiliate 토글
    DELETE /api/dashboard/admin/restaurants/<id>/ → 레코드 삭제
    """
    permission_classes = [IsAuthenticated]

    def _get_admin_restaurant(self, request, restaurant_id):
        if not bool(request.auth.get("is_admin", False)):
            return None, Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        try:
            return AffiliateRestaurant.objects.get(restaurant_id=int(restaurant_id)), None
        except (AffiliateRestaurant.DoesNotExist, ValueError):
            return None, Response({"detail": "식당을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, restaurant_id):
        r, err = self._get_admin_restaurant(request, restaurant_id)
        if err:
            return err
        is_affiliate = request.data.get("is_affiliate")
        if is_affiliate is None:
            return Response({"detail": "is_affiliate 값이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        r.is_affiliate = bool(is_affiliate)
        try:
            r.save(update_fields=["is_affiliate"])
        except Exception as e:
            logger.error(f"AdminRestaurantView PATCH error: {e}")
            return Response({"detail": "저장에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"success": True, "restaurant_id": r.restaurant_id, "is_affiliate": r.is_affiliate})

    def delete(self, request, restaurant_id):
        r, err = self._get_admin_restaurant(request, restaurant_id)
        if err:
            return err

        # 2차 비밀번호 검증
        secondary_pw = request.data.get("secondary_password", "")
        if not secondary_pw:
            return Response({"detail": "2차 비밀번호가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if not AdminConfig.check_password("secondary_password_hash", secondary_pw):
            return Response({"detail": "2차 비밀번호가 올바르지 않습니다."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            r.delete()
        except Exception as e:
            logger.error(f"AdminRestaurantView DELETE error: {e}")
            return Response({"detail": "삭제에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"success": True}, status=status.HTTP_200_OK)


class AdminPasswordView(APIView):
    """
    관리자 비밀번호 변경
    PATCH /api/dashboard/admin/password/
    Body: { type: "main"|"secondary", current_password: str, new_password: str }
    - type=main: 현재 비밀번호(환경변수 or DB) 검증 후 DB에 새 비밀번호 저장
    - type=secondary: 현재 2차 비밀번호(있으면) 검증 후 DB에 저장 (최초 설정 시 current_password 불필요)
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        import os
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)

        pw_type = request.data.get("type")
        current_password = request.data.get("current_password", "")
        new_password = request.data.get("new_password", "")

        if pw_type not in ("main", "secondary"):
            return Response({"detail": "type은 'main' 또는 'secondary'이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if not new_password or len(new_password) < 4:
            return Response({"detail": "새 비밀번호는 4자 이상이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        if pw_type == "main":
            # 현재 비밀번호 검증 (DB 우선, 없으면 환경변수)
            db_pw = AdminConfig.get("main_password_hash")
            if db_pw:
                valid = AdminConfig.check_password("main_password_hash", current_password)
            else:
                valid = current_password == os.getenv("DASHBOARD_ADMIN_PASSWORD", "")
            if not valid:
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_401_UNAUTHORIZED)
            AdminConfig.set_password("main_password_hash", new_password)

        else:  # secondary
            existing = AdminConfig.get("secondary_password_hash")
            if existing:
                if not AdminConfig.check_password("secondary_password_hash", current_password):
                    return Response({"detail": "현재 2차 비밀번호가 올바르지 않습니다."}, status=status.HTTP_401_UNAUTHORIZED)
            # 최초 설정 시에는 current_password 없어도 OK
            AdminConfig.set_password("secondary_password_hash", new_password)

        return Response({"success": True})


class DashboardStatsView(APIView):
    """
    홈 핵심 지표 (P0)
    GET /api/dashboard/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = bool(request.auth.get("is_admin", False))

        if is_admin:
            rid = request.query_params.get("restaurant_id")
            if not rid:
                return Response({"detail": "restaurant_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                restaurant = AffiliateRestaurant.objects.get(restaurant_id=int(rid))
            except (AffiliateRestaurant.DoesNotExist, ValueError):
                return Response({"detail": "식당을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
            restaurant_id = restaurant.restaurant_id
            restaurant_name = restaurant.name
            tier = "FREE"  # 관리자 뷰에서는 기본 FREE (OwnerProfile 없으므로)
        else:
            try:
                owner = request.user.owner_profile
            except OwnerProfile.DoesNotExist:
                return Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)
            restaurant_id = owner.restaurant_id
            restaurant_name = owner.restaurant.name
            tier = owner.tier

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        coupon_count = Coupon.objects.filter(
            restaurant_id=restaurant_id,
            status="REDEEMED",
            redeemed_at__gte=month_start,
        ).count()

        stamp_count = StampEvent.objects.filter(
            restaurant_id=restaurant_id,
            delta__gt=0,
            created_at__gte=month_start,
        ).count()

        revisit_count = (
            StampEvent.objects.filter(
                restaurant_id=restaurant_id,
                delta__gt=0,
                created_at__gte=month_start,
            )
            .values("user_id")
            .annotate(visits=Count("id"))
            .filter(visits__gte=2)
            .count()
        )

        loyal_count = (
            StampEvent.objects.filter(
                restaurant_id=restaurant_id,
                delta__gt=0,
            )
            .values("user_id")
            .annotate(visits=Count("id"))
            .filter(visits__gte=3)
            .count()
        )

        return Response({
            "restaurant_id": restaurant_id,
            "restaurant_name": restaurant_name,
            "tier": tier,
            "month": now.strftime("%Y-%m"),
            "stats": {
                "revisit_this_month": revisit_count,
                "loyal_total": loyal_count,
                "coupon_redeemed_this_month": coupon_count,
                "stamp_earned_this_month": stamp_count,
            },
        })
