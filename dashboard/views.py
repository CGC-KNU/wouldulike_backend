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

import uuid
import re
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from coupons.models import MerchantPin, Coupon, StampEvent, CouponType, RestaurantCouponBenefit, StampRewardRule
from datetime import date as date_type, timedelta
from notifications.models import Notification, RestaurantNotificationSchedule
from accounts.models import UserRestaurantWishlist
from notifications.utils import send_notification
from guests.models import GuestUser
from django.db import models as db_models
from django.db.models import Q
from restaurants.models import AffiliateRestaurant
from accounts.models import User
from trends.models import Trend, PopupCampaign
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
    MAX_IMAGES = 5

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
            "s3_image_urls": list(r.s3_image_urls) if r.s3_image_urls else [],
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

        # s3_image_urls 별도 처리 (최대 MAX_IMAGES장)
        if "s3_image_urls" in request.data:
            urls = request.data["s3_image_urls"]
            if not isinstance(urls, list):
                return Response({"detail": "s3_image_urls는 배열이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
            if len(urls) > self.MAX_IMAGES:
                return Response(
                    {"detail": f"이미지는 최대 {self.MAX_IMAGES}장까지 등록할 수 있습니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            r.s3_image_urls = urls
            updated.append("s3_image_urls")

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


class PresignedUploadView(APIView):
    """
    S3 Presigned PUT URL 발급 — 클라이언트가 직접 S3에 업로드
    POST /api/dashboard/images/presign/
    Body: { restaurant_id: int, filename: str, content_type: str }
    Response: { upload_url: str, public_url: str }
    """
    permission_classes = [IsAuthenticated]

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    EXPIRES_IN = 300  # 5분

    def post(self, request):
        import os
        restaurant_id = request.data.get("restaurant_id")
        filename = request.data.get("filename", "image.jpg")
        content_type = request.data.get("content_type", "image/jpeg")

        if content_type not in self.ALLOWED_TYPES:
            return Response({"detail": "허용되지 않는 파일 형식입니다. (jpeg/png/webp)"}, status=status.HTTP_400_BAD_REQUEST)

        # 권한 확인 — 관리자이거나 해당 식당 점주
        is_admin = bool(request.auth.get("is_admin", False))
        if not is_admin:
            try:
                owner_restaurant_id = request.user.owner_profile.restaurant_id
                if str(owner_restaurant_id) != str(restaurant_id):
                    return Response({"detail": "권한이 없습니다."}, status=status.HTTP_403_FORBIDDEN)
            except OwnerProfile.DoesNotExist:
                return Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

        # S3 키 생성
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        safe_name = re.sub(r"[^\w가-힣.-]", "_", base_name)[:40]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]

        upload_type = request.data.get("upload_type", "restaurant")
        if upload_type in ("banner", "popup", "trend"):
            if not is_admin:
                return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
            prefix = "trend_images" if upload_type == "trend" else f"{upload_type}s"
            key = f"{prefix}/{timestamp}_{safe_name}_{uid}.{ext}"
        else:
            key = f"restaurants/{restaurant_id}/{timestamp}_{safe_name}_{uid}.{ext}"

        bucket = os.getenv("AWS_STORAGE_BUCKET_NAME", "wouldulike-default-bucket-lunching")
        region = os.getenv("AWS_S3_REGION_NAME", "ap-northeast-2")

        try:
            s3 = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
            upload_url = s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=self.EXPIRES_IN,
            )
            public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
            return Response({"upload_url": upload_url, "public_url": public_url})
        except ClientError as e:
            logger.error(f"PresignedUploadView error: {e}")
            return Response({"detail": "S3 URL 생성에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminBannerPopupView(APIView):
    """
    앱 배너 / 팝업 이미지 관리 (관리자 전용) — URL 배열로 저장
    GET  /api/dashboard/admin/banner-popup/ → { banner_urls: [...], popup_urls: [...] }
    PATCH /api/dashboard/admin/banner-popup/ → body: { banner_urls?: [...], popup_urls?: [...] }
    """
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _load_urls(self, key):
        """
        key: 현재 키 (예: banner_image_urls)
        하위 호환: 이전 버전에서 단수형 키(banner_image_url)에 단일 URL로 저장한 경우도 처리
        """
        import json
        obj = AdminConfig.get(key)
        if not obj or not obj.value:
            # 구버전 단수 키 fallback (banner_image_urls → banner_image_url)
            old_key = key[:-1] if key.endswith("s") else key
            if old_key != key:
                obj = AdminConfig.get(old_key)
            if not obj or not obj.value:
                return []
            # 단수 키에 저장된 값: JSON 배열이면 그대로, 단일 URL이면 배열로 감쌈
            try:
                val = json.loads(obj.value)
                return val if isinstance(val, list) else ([val] if val else [])
            except (json.JSONDecodeError, TypeError):
                return [obj.value] if obj.value else []
        try:
            val = json.loads(obj.value)
            return val if isinstance(val, list) else ([val] if val else [])
        except (json.JSONDecodeError, TypeError):
            return [obj.value] if obj.value else []

    def get(self, request):
        if err := self._require_admin(request):
            return err
        import json
        banner_urls = self._load_urls("banner_image_urls")
        popup_urls = self._load_urls("popup_image_urls")
        # 구버전 단수 키 데이터가 있으면 복수 키로 자동 마이그레이션
        for key, urls in (("banner_image_urls", banner_urls), ("popup_image_urls", popup_urls)):
            if urls and not AdminConfig.get(key):
                AdminConfig.objects.update_or_create(
                    key=key,
                    defaults={"value": json.dumps(urls, ensure_ascii=False)},
                )
        return Response({
            "banner_urls": banner_urls,
            "popup_urls": popup_urls,
        })

    def patch(self, request):
        if err := self._require_admin(request):
            return err
        import json
        updated = []
        for field, key in (
            ("banner_urls", "banner_image_urls"),
            ("popup_urls", "popup_image_urls"),
        ):
            if field in request.data:
                urls = request.data[field]
                if not isinstance(urls, list):
                    return Response(
                        {"detail": f"{field}는 배열이어야 합니다."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                AdminConfig.objects.update_or_create(
                    key=key,
                    defaults={"value": json.dumps(urls, ensure_ascii=False)},
                )
                updated.append(field)
        if not updated:
            return Response({"detail": "변경할 내용이 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True, "updated": updated})


class AdminTrendView(APIView):
    """
    배너(트렌드) CRUD — 관리자 전용  (trends.Trend 모델)
    GET    /api/dashboard/admin/trends/
    POST   /api/dashboard/admin/trends/
    PATCH  /api/dashboard/admin/trends/<pk>/
    DELETE /api/dashboard/admin/trends/<pk>/
    """
    permission_classes = [IsAuthenticated]
    BUCKET = "wouldulike-default-bucket-lunching"
    REGION = "ap-northeast-2"

    def _require_admin(self, request):
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _image_url(self, trend):
        if not trend.image or not trend.image.name:
            return None
        name = trend.image.name
        if name.startswith(("http://", "https://")):
            return name
        return f"https://{self.BUCKET}.s3.{self.REGION}.amazonaws.com/{name}"

    def _serialize(self, t):
        return {
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "image_url": self._image_url(t),
            "blog_link": t.blog_link,
            "display_order": t.display_order,
            "created_at": t.created_at.isoformat(),
        }

    def get(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if pk:
            try:
                return Response(self._serialize(Trend.objects.get(pk=pk)))
            except Trend.DoesNotExist:
                return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)
        return Response([self._serialize(t) for t in Trend.objects.all().order_by("display_order", "-created_at")])

    def post(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        data = request.data
        title = (data.get("title") or "").strip()
        if not title:
            return Response({"detail": "title이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            t = Trend.objects.create(
                title=title,
                description=(data.get("description") or "").strip(),
                image=(data.get("image_url") or "").strip(),
                blog_link=(data.get("blog_link") or "").strip(),
                display_order=int(data.get("display_order", 0) or 0),
            )
            return Response(self._serialize(t), status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"AdminTrendView POST error: {e}")
            return Response({"detail": "생성에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            t = Trend.objects.get(pk=pk)
        except Trend.DoesNotExist:
            return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data
        updated = []
        for field in ("title", "description", "blog_link"):
            if field in data:
                setattr(t, field, data[field])
                updated.append(field)
        if "image_url" in data and data["image_url"]:
            t.image = data["image_url"]
            updated.append("image")
        if "display_order" in data:
            t.display_order = int(data["display_order"] or 0)
            updated.append("display_order")
        if updated:
            t.save(update_fields=updated)
        return Response(self._serialize(t))

    def delete(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            Trend.objects.get(pk=pk).delete()
            return Response({"success": True})
        except Trend.DoesNotExist:
            return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)


class AdminPopupCampaignView(APIView):
    """
    팝업 캠페인 CRUD — 관리자 전용  (trends.PopupCampaign 모델)
    GET    /api/dashboard/admin/popup-campaigns/
    POST   /api/dashboard/admin/popup-campaigns/
    PATCH  /api/dashboard/admin/popup-campaigns/<pk>/
    DELETE /api/dashboard/admin/popup-campaigns/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _serialize(self, p):
        return {
            "id": p.id,
            "title": p.title,
            "image_url": p.image_url,
            "instagram_url": p.instagram_url,
            "start_at": p.start_at.isoformat(),
            "end_at": p.end_at.isoformat(),
            "is_active": p.is_active,
            "display_order": p.display_order,
            "created_at": p.created_at.isoformat(),
        }

    @staticmethod
    def _parse_dt(s):
        from django.utils import timezone as tz
        from datetime import datetime
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return tz.make_aware(datetime.strptime(str(s).strip(), fmt), tz.utc)
            except ValueError:
                continue
        raise ValueError(f"날짜 형식 오류: {s}  (YYYY-MM-DDTHH:MM 형식을 사용하세요)")

    def get(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if pk:
            try:
                return Response(self._serialize(PopupCampaign.objects.get(pk=pk)))
            except PopupCampaign.DoesNotExist:
                return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)
        return Response([self._serialize(p) for p in PopupCampaign.objects.all().order_by("display_order", "-created_at")])

    def post(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        data = request.data
        title = (data.get("title") or "").strip()
        image_url = (data.get("image_url") or "").strip()
        start_at = data.get("start_at")
        end_at = data.get("end_at")
        if not title or not image_url or not start_at or not end_at:
            return Response({"detail": "title, image_url, start_at, end_at이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start = self._parse_dt(start_at)
            end = self._parse_dt(end_at)
            if end <= start:
                return Response({"detail": "end_at은 start_at보다 이후여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
            p = PopupCampaign.objects.create(
                title=title,
                image_url=image_url,
                instagram_url=(data.get("instagram_url") or "").strip(),
                start_at=start,
                end_at=end,
                is_active=bool(data.get("is_active", True)),
                display_order=int(data.get("display_order", 0) or 0),
            )
            return Response(self._serialize(p), status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"AdminPopupCampaignView POST error: {e}")
            return Response({"detail": "생성에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            p = PopupCampaign.objects.get(pk=pk)
        except PopupCampaign.DoesNotExist:
            return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data
        updated = []
        for field in ("title", "image_url", "instagram_url", "is_active"):
            if field in data:
                setattr(p, field, data[field])
                updated.append(field)
        if "display_order" in data:
            p.display_order = int(data["display_order"] or 0)
            updated.append("display_order")
        try:
            if "start_at" in data:
                p.start_at = self._parse_dt(data["start_at"])
                updated.append("start_at")
            if "end_at" in data:
                p.end_at = self._parse_dt(data["end_at"])
                updated.append("end_at")
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if p.end_at <= p.start_at:
            return Response({"detail": "end_at은 start_at보다 이후여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        if updated:
            p.save(update_fields=updated)
        return Response(self._serialize(p))

    def delete(self, request, pk=None):
        if err := self._require_admin(request):
            return err
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            PopupCampaign.objects.get(pk=pk).delete()
            return Response({"success": True})
        except PopupCampaign.DoesNotExist:
            return Response({"detail": "없습니다."}, status=status.HTTP_404_NOT_FOUND)


class AdminBannerPopupS3ScanView(APIView):
    """
    S3 banners/ / popups/ 폴더에 실제 업로드된 파일 목록 반환 (복구용)
    GET /api/dashboard/admin/banner-popup/s3-scan/
    Response: { banners: [url, ...], popups: [url, ...] }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        import os
        bucket = os.getenv("AWS_STORAGE_BUCKET_NAME", "wouldulike-default-bucket-lunching")
        region = os.getenv("AWS_S3_REGION_NAME", "ap-northeast-2")
        try:
            s3 = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
            result = {}
            for prefix in ("banners/", "popups/"):
                resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
                urls = [
                    f"https://{bucket}.s3.{region}.amazonaws.com/{obj['Key']}"
                    for obj in resp.get("Contents", [])
                    if obj.get("Size", 0) > 0
                ]
                result[prefix.rstrip("/")] = urls
            return Response(result)
        except ClientError as e:
            logger.error(f"AdminBannerPopupS3ScanView error: {e}")
            return Response({"detail": "S3 조회에 실패했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminConfigDebugView(APIView):
    """
    AdminConfig 테이블 전체 키 목록 반환 (진단용)
    GET /api/dashboard/admin/config-debug/
    Response: { records: [{key, value_preview}] }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not bool(request.auth.get("is_admin", False)):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        records = [
            {
                "key": obj.key,
                "value_preview": (obj.value or "")[:200] if obj.value else None,
            }
            for obj in AdminConfig.objects.all().order_by("key")
        ]
        return Response({"records": records, "count": len(records)})


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


# ──────────────────────────────────────────────────────────
# 쿠폰 타입 목록
# ──────────────────────────────────────────────────────────
class CouponTypesView(APIView):
    """
    GET /api/dashboard/coupon-types/
    사용 가능한 CouponType 목록 반환 (admin·점주 공용)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = bool(request.auth.get("is_admin", False))
        if not is_admin:
            try:
                _ = request.user.owner_profile
            except OwnerProfile.DoesNotExist:
                return Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

        types = CouponType.objects.all().order_by("code")
        return Response([
            {
                "id": ct.id,
                "code": ct.code,
                "title": ct.title,
                "benefit_json": ct.benefit_json,
                "valid_days": ct.valid_days,
            }
            for ct in types
        ])


# ──────────────────────────────────────────────────────────
# 식당별 쿠폰 혜택 (RestaurantCouponBenefit) CRUD
# ──────────────────────────────────────────────────────────
class RestaurantCouponBenefitsView(APIView):
    """
    GET/POST   /api/dashboard/coupon-benefits/
    PATCH/DELETE /api/dashboard/coupon-benefits/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def _get_rid(self, request):
        """admin: ?restaurant_id 파라미터, 점주: owner_profile에서."""
        is_admin = bool(request.auth.get("is_admin", False))
        if is_admin:
            rid = request.query_params.get("restaurant_id") or request.data.get("restaurant_id")
            if not rid:
                return None, Response({"detail": "restaurant_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                return int(rid), None
            except (TypeError, ValueError):
                return None, Response({"detail": "restaurant_id는 정수여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                return request.user.owner_profile.restaurant_id, None
            except OwnerProfile.DoesNotExist:
                return None, Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

    def _serialize(self, b):
        return {
            "id": b.id,
            "coupon_type_code": b.coupon_type.code,
            "coupon_type_title": b.coupon_type.title,
            "benefit_json": b.benefit_json or b.coupon_type.benefit_json,
            "title": b.title,
            "subtitle": b.subtitle,
            "notes": b.notes,
            "sort_order": b.sort_order,
            "active": b.active,
            "updated_at": b.updated_at.isoformat(),
        }

    def get(self, request, pk=None):
        rid, err = self._get_rid(request)
        if err:
            return err
        benefits = (
            RestaurantCouponBenefit.objects
            .select_related("coupon_type")
            .filter(restaurant_id=rid)
            .order_by("sort_order", "id")
        )
        return Response([self._serialize(b) for b in benefits])

    def post(self, request, pk=None):
        rid, err = self._get_rid(request)
        if err:
            return err

        coupon_type_code = (request.data.get("coupon_type_code") or "").strip()
        title = (request.data.get("title") or "").strip()
        if not coupon_type_code or not title:
            return Response({"detail": "coupon_type_code와 title은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ct = CouponType.objects.get(code=coupon_type_code)
        except CouponType.DoesNotExist:
            return Response({"detail": "존재하지 않는 쿠폰 타입입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # sort_order: 해당 coupon_type × restaurant 조합의 최대값 + 1
        sort_order = request.data.get("sort_order")
        if sort_order is None:
            agg = RestaurantCouponBenefit.objects.filter(
                restaurant_id=rid, coupon_type=ct
            ).aggregate(m=db_models.Max("sort_order"))
            sort_order = (agg["m"] or 0) + 1

        try:
            benefit = RestaurantCouponBenefit.objects.create(
                coupon_type=ct,
                restaurant_id=rid,
                sort_order=int(sort_order),
                title=title,
                subtitle=request.data.get("subtitle", ""),
                notes=request.data.get("notes", ""),
                active=bool(request.data.get("active", True)),
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self._serialize(benefit), status=status.HTTP_201_CREATED)

    def patch(self, request, pk=None):
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        rid, err = self._get_rid(request)
        if err:
            return err

        try:
            benefit = RestaurantCouponBenefit.objects.select_related("coupon_type").get(
                pk=pk, restaurant_id=rid
            )
        except RestaurantCouponBenefit.DoesNotExist:
            return Response({"detail": "찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        for field in ("title", "subtitle", "notes", "sort_order", "active"):
            if field in request.data:
                val = request.data[field]
                if field == "sort_order":
                    val = int(val)
                elif field == "active":
                    val = bool(val)
                setattr(benefit, field, val)

        benefit.save()
        return Response(self._serialize(benefit))

    def delete(self, request, pk=None):
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        rid, err = self._get_rid(request)
        if err:
            return err

        try:
            benefit = RestaurantCouponBenefit.objects.get(pk=pk, restaurant_id=rid)
        except RestaurantCouponBenefit.DoesNotExist:
            return Response({"detail": "찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        benefit.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────
# 식당별 스탬프 보상 규칙 (StampRewardRule) 조회 & 저장
# ──────────────────────────────────────────────────────────
class StampRewardRuleView(APIView):
    """
    GET   /api/dashboard/stamp-rule/
    PATCH /api/dashboard/stamp-rule/    (없으면 생성, 있으면 업데이트)
    """
    permission_classes = [IsAuthenticated]

    def _get_rid(self, request):
        is_admin = bool(request.auth.get("is_admin", False))
        if is_admin:
            rid = request.query_params.get("restaurant_id") or request.data.get("restaurant_id")
            if not rid:
                return None, Response({"detail": "restaurant_id가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                return int(rid), None
            except (TypeError, ValueError):
                return None, Response({"detail": "restaurant_id는 정수여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                return request.user.owner_profile.restaurant_id, None
            except OwnerProfile.DoesNotExist:
                return None, Response({"detail": "점주 계정이 아닙니다."}, status=status.HTTP_403_FORBIDDEN)

    def _serialize(self, rule):
        return {
            "id": rule.id,
            "restaurant_id": rule.restaurant_id,
            "rule_type": rule.rule_type,
            "config_json": rule.config_json,
            "active": rule.active,
            "updated_at": rule.updated_at.isoformat(),
        }

    def get(self, request):
        rid, err = self._get_rid(request)
        if err:
            return err
        try:
            rule = StampRewardRule.objects.get(restaurant_id=rid)
            return Response(self._serialize(rule))
        except StampRewardRule.DoesNotExist:
            return Response({"exists": False}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        rid, err = self._get_rid(request)
        if err:
            return err

        rule_type = request.data.get("rule_type", "THRESHOLD")
        if rule_type not in ("THRESHOLD", "VISIT"):
            return Response({"detail": "rule_type은 THRESHOLD 또는 VISIT이어야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        config_json = request.data.get("config_json")
        if not isinstance(config_json, dict):
            return Response({"detail": "config_json은 객체여야 합니다."}, status=status.HTTP_400_BAD_REQUEST)

        active = bool(request.data.get("active", True))

        rule, created = StampRewardRule.objects.update_or_create(
            restaurant_id=rid,
            defaults={
                "rule_type": rule_type,
                "config_json": config_json,
                "active": active,
            },
        )
        return Response(
            self._serialize(rule),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────
# 관리자 알림 관리 API
# ──────────────────────────────────────────────────────────────
TEST_KAKAO_ID = 4424485763  # 개발자 테스트 전용 카카오 ID


class AdminNotificationsView(APIView):
    """관리자 알림 예약 CRUD + 즉시발송"""

    def _check_admin(self, request):
        if not request.auth or not request.auth.get("is_admin"):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def _serialize(self, n):
        lines = (n.content or "").splitlines()
        return {
            "id": n.id,
            "title": lines[0] if lines else "",
            "body": "\n".join(lines[1:]) if len(lines) > 1 else "",
            "content": n.content,
            "scheduled_time": n.scheduled_time.isoformat(),
            "sent": n.sent,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            "target_kakao_ids": n.target_kakao_ids,
            "test_only": n.target_kakao_ids == [TEST_KAKAO_ID],
            "created_at": n.created_at.isoformat(),
        }

    def get(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err
        notifications = Notification.objects.order_by("-scheduled_time")[:50]
        return Response([self._serialize(n) for n in notifications])

    def post(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err

        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        scheduled_time_str = request.data.get("scheduled_time")
        test_only = bool(request.data.get("test_only", True))  # 기본값: 테스트 모드

        if not title:
            return Response({"detail": "제목(title)은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)
        if not scheduled_time_str:
            return Response({"detail": "scheduled_time은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from datetime import datetime
            # ISO 8601 파싱 (타임존 포함/미포함 모두 처리)
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return Response({"detail": "scheduled_time 형식이 올바르지 않습니다. (ISO 8601)"}, status=status.HTTP_400_BAD_REQUEST)

        content = f"{title}\n{body}" if body else title
        target_kakao_ids = [TEST_KAKAO_ID] if test_only else None

        notification = Notification.objects.create(
            content=content,
            scheduled_time=scheduled_time,
            target_kakao_ids=target_kakao_ids,
        )
        return Response(self._serialize(notification), status=status.HTTP_201_CREATED)

    def delete(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err
        if not pk:
            return Response({"detail": "pk가 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            notification = Notification.objects.get(id=pk)
        except Notification.DoesNotExist:
            return Response({"detail": "알림을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
        if notification.sent:
            return Response({"detail": "이미 발송된 알림은 삭제할 수 없습니다."}, status=status.HTTP_400_BAD_REQUEST)
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminNotificationSendNowView(APIView):
    """특정 알림 즉시 발송 (테스트 전용: target_kakao_ids 필수)"""

    def _check_admin(self, request):
        if not request.auth or not request.auth.get("is_admin"):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def post(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err
        try:
            notification = Notification.objects.get(id=pk)
        except Notification.DoesNotExist:
            return Response({"detail": "알림을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        if notification.sent:
            return Response({"detail": "이미 발송된 알림입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # target_kakao_ids 없으면 전체 발송 → 위험하므로 API에서는 금지
        if not notification.target_kakao_ids:
            return Response(
                {"detail": "즉시발송은 target_kakao_ids가 설정된 알림에만 허용됩니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # FCM 토큰 수집
        user_tokens = list(
            User.objects.filter(kakao_id__in=notification.target_kakao_ids)
            .exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .values_list("fcm_token", flat=True)
        )
        guest_tokens = list(
            GuestUser.objects.filter(linked_user__kakao_id__in=notification.target_kakao_ids)
            .exclude(fcm_token__isnull=True)
            .exclude(fcm_token="")
            .values_list("fcm_token", flat=True)
        )
        tokens = list(set(user_tokens + guest_tokens))

        if not tokens:
            return Response(
                {"detail": "대상 사용자의 FCM 토큰이 없습니다."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 알림 발송
        lines = (notification.content or "").splitlines()
        title = lines[0] if lines else None
        result = send_notification(tokens, notification.content, title=title)

        # 발송 완료 처리
        notification.sent = True
        notification.sent_at = timezone.now()
        notification.save(update_fields=["sent", "sent_at"])

        return Response({
            "success": result.get("success", 0) if result else 0,
            "failure": result.get("failure", 0) if result else 0,
            "tokens_tried": len(tokens),
            "notification": {
                "id": notification.id,
                "content": notification.content,
                "sent_at": notification.sent_at.isoformat(),
            },
        })


# ─────────────────────────────────────────────────────────
# 식당 알림 예약 (점주 / 관리자 공통 유틸)
# ─────────────────────────────────────────────────────────

def _slot_to_utc(d, slot: str):
    """KST 정오(12:00) = UTC 03:00 / KST 저녁(18:00) = UTC 09:00"""
    from django.utils.timezone import make_aware
    import pytz
    hour_utc = 3 if slot == "noon" else 9
    naive = datetime(d.year, d.month, d.day, hour_utc, 0, 0)
    return make_aware(naive, pytz.UTC)


def _serialize_schedule(s):
    return {
        "id": s.id,
        "restaurant_id": s.restaurant_id,
        "restaurant_name": s.restaurant_name,
        "date": s.date.isoformat(),
        "slot": s.slot,
        "content": s.content,
        "scheduled_datetime": s.scheduled_datetime.isoformat(),
        "sent": s.sent,
        "sent_at": s.sent_at.isoformat() if s.sent_at else None,
        "created_by_id": s.created_by_id,
    }


class OwnerNotificationScheduleView(APIView):
    """점주: 자신의 식당 알림 예약 조회 · 생성 · 삭제"""

    def _get_restaurant_id(self, request):
        if not request.auth or not request.auth.get("is_owner"):
            return None, Response({"detail": "점주 권한이 필요합니다."}, status=403)
        rid = request.auth.get("restaurant_id")
        if not rid:
            return None, Response({"detail": "restaurant_id를 찾을 수 없습니다."}, status=403)
        return int(rid), None

    def get(self, request):
        rid, err = self._get_restaurant_id(request)
        if err:
            return err
        year = int(request.query_params.get("year", date_type.today().year))
        month = int(request.query_params.get("month", date_type.today().month))
        qs = RestaurantNotificationSchedule.objects.filter(
            restaurant_id=rid, date__year=year, date__month=month
        ).order_by("scheduled_datetime")
        return Response([_serialize_schedule(s) for s in qs])

    def post(self, request):
        rid, err = self._get_restaurant_id(request)
        if err:
            return err
        slot = request.data.get("slot")
        date_str = request.data.get("date")
        content = (request.data.get("content") or "").strip()

        if slot not in ("noon", "evening"):
            return Response({"detail": "slot은 noon 또는 evening이어야 합니다."}, status=400)
        if not date_str or not content:
            return Response({"detail": "date와 content가 필요합니다."}, status=400)
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)."}, status=400)
        if d < date_type.today():
            return Response({"detail": "과거 날짜는 예약할 수 없습니다."}, status=400)

        try:
            restaurant = AffiliateRestaurant.objects.get(restaurant_id=rid)
            name = restaurant.name
        except AffiliateRestaurant.DoesNotExist:
            name = f"식당#{rid}"

        try:
            s = RestaurantNotificationSchedule.objects.create(
                restaurant_id=rid,
                restaurant_name=name,
                date=d,
                slot=slot,
                content=content,
                scheduled_datetime=_slot_to_utc(d, slot),
                created_by=request.user,
            )
        except Exception:
            return Response({"detail": "이미 해당 날짜/시간대에 예약이 존재합니다."}, status=409)
        return Response(_serialize_schedule(s), status=201)

    def delete(self, request, pk=None):
        rid, err = self._get_restaurant_id(request)
        if err:
            return err
        try:
            s = RestaurantNotificationSchedule.objects.get(pk=pk, restaurant_id=rid)
        except RestaurantNotificationSchedule.DoesNotExist:
            return Response({"detail": "예약을 찾을 수 없습니다."}, status=404)
        if s.sent:
            return Response({"detail": "이미 발송된 알림은 취소할 수 없습니다."}, status=400)
        s.delete()
        return Response(status=204)


class AdminRestaurantNotificationView(APIView):
    """관리자: 모든 식당 알림 예약 조회 · 수정 · 삭제"""

    def _check_admin(self, request):
        if not request.auth or not request.auth.get("is_admin"):
            return Response({"detail": "관리자 권한이 필요합니다."}, status=403)
        return None

    def get(self, request):
        err = self._check_admin(request)
        if err:
            return err
        year = int(request.query_params.get("year", date_type.today().year))
        month = int(request.query_params.get("month", date_type.today().month))
        qs = RestaurantNotificationSchedule.objects.filter(
            date__year=year, date__month=month
        ).order_by("scheduled_datetime")
        return Response([_serialize_schedule(s) for s in qs])

    def put(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err
        try:
            s = RestaurantNotificationSchedule.objects.get(pk=pk)
        except RestaurantNotificationSchedule.DoesNotExist:
            return Response({"detail": "예약을 찾을 수 없습니다."}, status=404)
        if s.sent:
            return Response({"detail": "이미 발송된 알림은 수정할 수 없습니다."}, status=400)
        if "content" in request.data:
            s.content = (request.data["content"] or "").strip()
        if "date" in request.data or "slot" in request.data:
            date_str = request.data.get("date", s.date.isoformat())
            slot = request.data.get("slot", s.slot)
            if slot not in ("noon", "evening"):
                return Response({"detail": "slot 값이 올바르지 않습니다."}, status=400)
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "날짜 형식이 올바르지 않습니다."}, status=400)
            s.date = d
            s.slot = slot
            s.scheduled_datetime = _slot_to_utc(d, slot)
        s.save()
        return Response(_serialize_schedule(s))

    def delete(self, request, pk=None):
        err = self._check_admin(request)
        if err:
            return err
        try:
            s = RestaurantNotificationSchedule.objects.get(pk=pk)
        except RestaurantNotificationSchedule.DoesNotExist:
            return Response({"detail": "예약을 찾을 수 없습니다."}, status=404)
        if s.sent:
            return Response({"detail": "이미 발송된 알림은 취소할 수 없습니다."}, status=400)
        s.delete()
        return Response(status=204)
