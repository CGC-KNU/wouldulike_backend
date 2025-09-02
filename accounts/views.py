import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

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
