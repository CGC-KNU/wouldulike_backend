import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import UserSerializer
from .jwt_utils import generate_tokens_for_user
from .utils import merge_guest_data


class KakaoLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get('access_token')
        guest_uuid = request.data.get('guest_uuid')
        if not access_token:
            return Response({'detail': 'access_token is required'}, status=status.HTTP_400_BAD_REQUEST)

        headers = {'Authorization': f'Bearer {access_token}'}
        kakao_response = requests.get('https://kapi.kakao.com/v2/user/me', headers=headers)

        if kakao_response.status_code == 401:
            return Response({'detail': 'Invalid or expired token'}, status=status.HTTP_401_UNAUTHORIZED)
        if kakao_response.status_code != 200:
            return Response({'detail': 'Kakao API error'}, status=status.HTTP_502_BAD_GATEWAY)

        data = kakao_response.json()
        kakao_id = data.get('id')
        kakao_account = data.get('kakao_account', {})
        profile = kakao_account.get('profile', {})

        email = kakao_account.get('email')
        nickname = profile.get('nickname')
        profile_image_url = profile.get('profile_image_url')

        user, created = User.objects.update_or_create(
            kakao_id=kakao_id,
            defaults={
                'email': email,
                'nickname': nickname,
                'profile_image_url': profile_image_url,
            }
        )

        if guest_uuid:
            merge_guest_data(guest_uuid, user)

        tokens = generate_tokens_for_user(user)
        serializer = UserSerializer(user)
        return Response({'token': tokens, 'user': serializer.data, 'is_new': created})


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