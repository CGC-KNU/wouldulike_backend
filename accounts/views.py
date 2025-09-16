import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import os

from .models import User
from .jwt_utils import generate_tokens_for_user
from .utils import merge_guest_data


class KakaoLoginView(APIView):
    # Kakao 로그인은 로그인 전 엔드포인트이므로 JWT 인증 비적용
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # 요청 스펙: JSON body로 access_token(필수), guest_uuid(선택)
        access_token = request.data.get('access_token') or request.data.get('accessToken')
        guest_uuid = request.data.get('guest_uuid')
        if not access_token:
            return Response({'detail': 'access_token is required'}, status=status.HTTP_400_BAD_REQUEST)

        # 1) Kakao 프로필 조회
        try:
            kakao_response = requests.get(
                'https://kapi.kakao.com/v2/user/me',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
        except Exception:
            return Response({'detail': 'kakao_api_error'}, status=status.HTTP_502_BAD_GATEWAY)

        if kakao_response.status_code != 200:
            return Response({'detail': 'kakao_token_invalid'}, status=status.HTTP_401_UNAUTHORIZED)

        data = kakao_response.json()
        kakao_id = data.get('id')
        kakao_account = data.get('kakao_account') or {}
        profile = kakao_account.get('profile') or {}
        nickname = profile.get('nickname') or ''
        profile_image_url = profile.get('profile_image_url') or ''

        if not kakao_id:
            return Response({'detail': 'kakao_profile_invalid'}, status=status.HTTP_400_BAD_REQUEST)

        # 2) 사용자 매핑/생성: kakao_id 기준
        user, created = User.objects.get_or_create(kakao_id=kakao_id)

        # guest_uuid가 있으면 게스트 데이터 귀속 (선택 구현)
        if guest_uuid:
            merge_guest_data(guest_uuid, user)

        # 3) JWT 발급
        tokens = generate_tokens_for_user(user)

        # 응답 스키마: token/access+refresh, user/id+nickname+profile_image_url
        resp = {
            'token': tokens,
            'user': {
                'id': user.id,
                'nickname': nickname,
                'profile_image_url': profile_image_url,
            },
            'is_new': created,
        }
        return Response(resp, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({'detail': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class UnlinkView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        headers = {'Authorization': f'KakaoAK {settings.KAKAO_ADMIN_KEY}'}
        data = {'target_id_type': 'user_id', 'target_id': user.kakao_id}
        response = requests.post('https://kapi.kakao.com/v1/user/unlink', headers=headers, data=data)
        if response.status_code != 200:
            return Response({'detail': 'Failed to unlink from Kakao'}, status=status.HTTP_502_BAD_GATEWAY)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class DevLoginView(APIView):
    """Development-only login to mint JWT for a given user.

    Pre-conditions (env or .env loaded in settings):
      - ALLOW_DEV_LOGIN=1
      - DEV_LOGIN_SECRET=<shared secret>

    Request (POST):
      Headers (prefer):
        - X-Dev-Login-Secret: <secret>
      or Body JSON:
        - secret: <secret>
        - kakao_id: <int> (required if user_id not provided)
        - user_id: <int> (optional alternative; DB pk)

    Response: { token: {access, refresh}, user: {id, nickname, profile_image_url}, is_new }
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if os.getenv("ALLOW_DEV_LOGIN") not in ("1", "true", "True"):  # safety gate
            return Response({"detail": "dev login not allowed"}, status=status.HTTP_403_FORBIDDEN)

        configured_secret = os.getenv("DEV_LOGIN_SECRET")
        provided_secret = (
            request.headers.get("X-Dev-Login-Secret")
            or request.data.get("secret")
            or request.query_params.get("secret")
        )
        if not configured_secret or not provided_secret or provided_secret != configured_secret:
            return Response({"detail": "invalid dev secret"}, status=status.HTTP_401_UNAUTHORIZED)

        # Identify target user
        user_id = request.data.get("user_id") or request.query_params.get("user_id")
        kakao_id = request.data.get("kakao_id") or request.query_params.get("kakao_id")

        user = None
        created = False
        try:
            if user_id:
                user = User.objects.get(id=int(user_id))
            elif kakao_id:
                kakao_id_int = int(kakao_id)
                user, created = User.objects.get_or_create(kakao_id=kakao_id_int)
            else:
                return Response({"detail": "kakao_id or user_id required"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"detail": "user not found"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"detail": "invalid id format"}, status=status.HTTP_400_BAD_REQUEST)

        tokens = generate_tokens_for_user(user)
        resp = {
            "token": tokens,
            "user": {
                "id": user.id,
                # Dev login has no Kakao profile; provide minimal placeholders
                "nickname": f"dev-{user.kakao_id}",
                "profile_image_url": "",
            },
            "is_new": created,
        }
        return Response(resp, status=status.HTTP_200_OK)
