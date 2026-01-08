import json
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import os
import logging

from .models import User
from guests.models import GuestUser
from .jwt_utils import generate_tokens_for_user
from coupons.service import issue_signup_coupon, issue_app_open_coupon
from .utils import merge_guest_data

logger = logging.getLogger(__name__)


def _serialize_user(user: User):
    favorites = user.favorite_restaurants
    favorites_payload = []
    if isinstance(favorites, list):
        favorites_payload = favorites
    elif favorites:
        try:
            favorites_payload = json.loads(favorites)
        except (TypeError, json.JSONDecodeError):
            favorites_payload = favorites

    return {
        'id': user.id,
        'kakao_id': user.kakao_id,
        'type_code': user.type_code,
        'favorite_restaurants': favorites_payload,
        'fcm_token': user.fcm_token,
        'preferences': user.preferences,
        'survey_responses': user.survey_responses,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
    }


class KakaoLoginView(APIView):
    # Kakao 로그인은 로그인 전 엔드포인트이므로 JWT 인증 비적용
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # 요청 스펙: JSON body로 access_token(필수), guest_uuid(선택)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
        try:
            access_token = request.data.get('access_token') or request.data.get('accessToken')
            guest_uuid = request.data.get('guest_uuid')
            
            logger.info(f'Login attempt - User-Agent: {user_agent}, IP: {client_ip}, Has token: {bool(access_token)}')
            
            if not access_token:
                logger.warning(f'Login failed: access_token missing - User-Agent: {user_agent}')
                return Response({'detail': 'access_token is required'}, status=status.HTTP_400_BAD_REQUEST)

            # 1) Kakao 프로필 조회
            try:
                kakao_response = requests.get(
                    'https://kapi.kakao.com/v2/user/me',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=10,
                )
            except requests.exceptions.Timeout:
                logger.error(f'Kakao API timeout - User-Agent: {user_agent}, IP: {client_ip}')
                return Response({'detail': 'kakao_api_error', 'code': 'timeout'}, status=status.HTTP_502_BAD_GATEWAY)
            except requests.exceptions.ConnectionError as e:
                logger.error(f'Kakao API connection error - User-Agent: {user_agent}, IP: {client_ip}, Error: {str(e)}')
                return Response({'detail': 'kakao_api_error', 'code': 'connection_error'}, status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:
                logger.error(f'Kakao API unexpected error - User-Agent: {user_agent}, IP: {client_ip}, Error: {str(e)}', exc_info=True)
                return Response({'detail': 'kakao_api_error', 'code': 'unknown'}, status=status.HTTP_502_BAD_GATEWAY)

            if kakao_response.status_code != 200:
                logger.warning(f'Kakao API returned non-200 status: {kakao_response.status_code} - User-Agent: {user_agent}, Response: {kakao_response.text[:200]}')
                return Response({'detail': 'kakao_token_invalid', 'code': f'http_{kakao_response.status_code}'}, status=status.HTTP_401_UNAUTHORIZED)

            # JSON 파싱 처리 (UTF-8 BOM 및 잘못된 MIME 타입 대비)
            try:
                data = kakao_response.json()
            except ValueError:
                raw_text = kakao_response.text
                data = None
                # Kakao가 간헐적으로 UTF-8 BOM이 포함된 텍스트나 JSON MIME이 아닌 응답을
                # 반환하는 경우를 대비해 content를 우선 활용한 수동 파싱을 시도한다.
                fallback_sources = [
                    kakao_response.content,
                    raw_text,
                ]
                for payload in fallback_sources:
                    if not payload:
                        continue
                    try:
                        cleaned_text = (
                            payload.decode('utf-8-sig') if isinstance(payload, (bytes, bytearray)) 
                            else str(payload).lstrip('\ufeff')
                        )
                        data = json.loads(cleaned_text)
                        logger.info(f'Successfully parsed Kakao response using fallback method - User-Agent: {user_agent}')
                        break
                    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                        continue
                
                if data is None:
                    logger.error(
                        'Failed to parse Kakao profile response',
                        extra={
                            'status_code': kakao_response.status_code,
                            'content_type': kakao_response.headers.get('Content-Type'),
                            'content_length': len(kakao_response.content or b''),
                            'text': raw_text[:500] if raw_text else None,
                            'user_agent': user_agent,
                            'client_ip': client_ip,
                        },
                    )
                    return Response({'detail': 'kakao_api_error', 'code': 'invalid_response'}, status=status.HTTP_502_BAD_GATEWAY)
            
            kakao_id = data.get('id')
            kakao_account = data.get('kakao_account') or {}
            profile = kakao_account.get('profile') or {}
            nickname = profile.get('nickname') or ''
            profile_image_url = profile.get('profile_image_url') or ''

            if not kakao_id:
                logger.warning(f'Kakao profile invalid (no kakao_id) - User-Agent: {user_agent}, Data: {str(data)[:200]}')
                return Response({'detail': 'kakao_profile_invalid'}, status=status.HTTP_400_BAD_REQUEST)

            # 2) 사용자 매핑/생성: kakao_id 기준
            try:
                user, created = User.objects.get_or_create(kakao_id=kakao_id)
            except Exception as e:
                logger.error(f'User creation/retrieval error - User-Agent: {user_agent}, IP: {client_ip}, Kakao ID: {kakao_id}, Error: {str(e)}', exc_info=True)
                return Response({'detail': 'internal_error', 'code': 'user_creation_failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # guest_uuid가 있으면 게스트 데이터 귀속 (선택 구현)
            if guest_uuid:
                try:
                    merge_guest_data(guest_uuid, user)
                except Exception as exc:
                    logger.warning(f'Failed to merge guest data - User-Agent: {user_agent}, Guest UUID: {guest_uuid}, Error: {str(exc)}', exc_info=True)
                    # 게스트 데이터 병합 실패는 치명적이지 않으므로 계속 진행

            signup_coupon_code = None
            if created:
                try:
                    coupon = issue_signup_coupon(user)
                    signup_coupon_code = coupon.code
                except Exception as exc:
                    logger.warning(
                        "failed to issue signup coupon for user %s: %s",
                        user.id,
                        exc,
                    )

            # 앱 접속(로그인) 쿠폰 발급 - 실패해도 로그인은 계속 진행
            try:
                issue_app_open_coupon(user)
            except Exception as exc:
                logger.warning(
                    "failed to issue app-open coupon on login for user %s: %s",
                    user.id,
                    exc,
                    exc_info=True,
                )

            # 3) JWT 발급
            try:
                tokens = generate_tokens_for_user(user)
                
                # 토큰 만료 시간 정보 추가
                refresh = RefreshToken(tokens['refresh'])
                access_token_obj = refresh.access_token
                tokens['access_expires_at'] = access_token_obj['exp']  # Unix timestamp
                tokens['refresh_expires_at'] = refresh['exp']  # Unix timestamp
            except Exception as e:
                logger.error(f'Token generation error - User-Agent: {user_agent}, IP: {client_ip}, User ID: {user.id}, Error: {str(e)}', exc_info=True)
                return Response({'detail': 'internal_error', 'code': 'token_generation_failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 응답 스키마: token/access+refresh, user/id+kakao_id+nickname+profile_image_url
            resp = {
                'token': tokens,
                'user': {
                    'id': user.id,
                    'kakao_id': user.kakao_id,
                    'nickname': nickname,
                    'profile_image_url': profile_image_url,
                },
                'is_new': created,
            }
            if signup_coupon_code:
                resp['signup_coupon_code'] = signup_coupon_code
            
            logger.info(f'Login successful - User-Agent: {user_agent}, IP: {client_ip}, User ID: {user.id}, Kakao ID: {kakao_id}, Is New: {created}')
            return Response(resp, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f'Unexpected error in KakaoLoginView - User-Agent: {user_agent}, IP: {client_ip}, Error: {str(e)}', exc_info=True)
            return Response({'detail': 'internal_error', 'code': 'unexpected_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomTokenRefreshView(BaseTokenRefreshView):
    """
    커스텀 토큰 갱신 뷰
    - 프론트엔드 요구사항에 맞는 응답 형식 제공
    - 에러 처리 개선
    - 로깅 추가
    - 동시성 처리 (같은 refresh token으로 동시 요청 시 동일한 새 토큰 반환)
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            logger.warning('Token refresh attempted without refresh token')
            return Response(
                {
                    'detail': 'Refresh token is required',
                    'code': 'invalid_request'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 동시성 처리: 같은 refresh token으로 짧은 시간 내 요청이 오면 캐시된 새 토큰 반환
        cache_key = f'token_refresh:{refresh_token[:20]}'
        cached_response = cache.get(cache_key)
        if cached_response:
            logger.info('Returning cached token refresh response')
            return Response(cached_response, status=status.HTTP_200_OK)

        try:
            # 기존 refresh token 검증
            refresh = RefreshToken(refresh_token)
            
            # ROTATE_REFRESH_TOKENS가 True일 때, 새로운 refresh token 생성
            # BaseTokenRefreshView의 로직을 따름
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # 기존 refresh token을 blacklist에 추가
                refresh.blacklist()
                # 새로운 refresh token 생성
                new_refresh = RefreshToken.for_user(refresh.user)
                new_access = new_refresh.access_token
                
                response_data = {
                    'access': str(new_access),
                    'refresh': str(new_refresh),
                    'access_expires_at': new_access['exp'],  # Unix timestamp
                    'refresh_expires_at': new_refresh['exp'],  # Unix timestamp
                }
            else:
                # ROTATE_REFRESH_TOKENS가 False인 경우 기존 refresh token 재사용
                new_access = refresh.access_token
                response_data = {
                    'access': str(new_access),
                    'refresh': str(refresh),
                    'access_expires_at': new_access['exp'],  # Unix timestamp
                    'refresh_expires_at': refresh['exp'],  # Unix timestamp
                }

            # 앱 접속(토큰 갱신) 쿠폰 발급 - 실패해도 토큰 갱신은 계속 진행
            try:
                user = getattr(refresh, "user", None)
                if user is not None:
                    issue_app_open_coupon(user)
            except Exception as exc:
                logger.warning(
                    "failed to issue app-open coupon on token refresh for user %s: %s",
                    getattr(user, "id", None),
                    exc,
                    exc_info=True,
                )

            # 캐시에 저장 (5초 동안 유효) - 동시 요청 방지
            cache.set(cache_key, response_data, timeout=5)

            logger.info(f'Token refreshed successfully for user {refresh.user.id}')
            return Response(response_data, status=status.HTTP_200_OK)

        except TokenError as e:
            error_code = 'token_not_valid'
            error_detail = 'Token is invalid or expired'
            
            if 'expired' in str(e).lower():
                error_code = 'token_expired'
                error_detail = 'Token is expired'
            
            logger.warning(f'Token refresh failed: {str(e)}')
            return Response(
                {
                    'detail': error_detail,
                    'code': error_code
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f'Unexpected error during token refresh: {str(e)}', exc_info=True)
            return Response(
                {
                    'detail': 'Token is invalid or expired',
                    'code': 'token_not_valid'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )


class TokenVerifyView(APIView):
    """
    토큰 검증 API
    - 현재 ACCESS_TOKEN이 유효한지 확인
    - 만료까지 남은 시간 정보 제공
    - 프론트엔드가 만료 전에 갱신할 수 있도록 도움
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """현재 토큰의 상태를 반환"""
        try:
            # 요청에서 토큰 추출
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return Response(
                    {
                        'detail': 'Invalid authorization header',
                        'code': 'invalid_request'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token_string = auth_header.split(' ')[1]
            access_token = AccessToken(token_string)
            
            # 만료 시간 정보 추출
            exp_timestamp = access_token['exp']
            now_timestamp = timezone.now().timestamp()
            expires_in = exp_timestamp - now_timestamp  # 초 단위
            
            return Response({
                'valid': True,
                'expires_at': exp_timestamp,
                'expires_in': max(0, int(expires_in)),  # 남은 시간 (초)
                'user_id': access_token['user_id'],
            }, status=status.HTTP_200_OK)
            
        except TokenError as e:
            return Response(
                {
                    'valid': False,
                    'detail': 'Token is invalid or expired',
                    'code': 'token_not_valid'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f'Token verification failed: {str(e)}', exc_info=True)
            return Response(
                {
                    'valid': False,
                    'detail': 'Token verification failed',
                    'code': 'token_not_valid'
                },
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {
                    'detail': 'Refresh token is required',
                    'code': 'invalid_request'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f'User {request.user.id} logged out successfully')
        except TokenError as e:
            logger.warning(f'Logout failed: Invalid refresh token - {str(e)}')
            return Response(
                {
                    'detail': 'Invalid token',
                    'code': 'token_not_valid'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'Unexpected error during logout: {str(e)}', exc_info=True)
            return Response(
                {
                    'detail': 'Invalid token',
                    'code': 'token_not_valid'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
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
        
        # 토큰 만료 시간 정보 추가
        refresh = RefreshToken(tokens['refresh'])
        access_token = refresh.access_token
        tokens['access_expires_at'] = access_token['exp']  # Unix timestamp
        tokens['refresh_expires_at'] = refresh['exp']  # Unix timestamp
        
        resp = {
            "token": tokens,
            "user": {
                "id": user.id,
                "kakao_id": user.kakao_id,
                # Dev login has no Kakao profile; provide minimal placeholders
                "nickname": f"dev-{user.kakao_id}",
                "profile_image_url": "",
            },
            "is_new": created,
        }
        return Response(resp, status=status.HTTP_200_OK)


class UserMeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_serialize_user(request.user), status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        data = request.data or {}
        update_fields = set()

        if 'type_code' in data:
            type_code = data.get('type_code')
            if type_code:
                type_code = str(type_code).strip().upper()
                if len(type_code) != 4:
                    return Response({'detail': 'type_code must be exactly 4 characters'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                type_code = None
            if type_code != user.type_code:
                user.type_code = type_code
                update_fields.add('type_code')

        if 'favorite_restaurants' in data:
            favorites = data.get('favorite_restaurants')
            if favorites in (None, ''):
                serialized_favorites = None
            elif isinstance(favorites, list):
                serialized_favorites = json.dumps(favorites)
            elif isinstance(favorites, str):
                serialized_favorites = favorites
            else:
                return Response({'detail': 'favorite_restaurants must be a list, string, or null'}, status=status.HTTP_400_BAD_REQUEST)

            if serialized_favorites != user.favorite_restaurants:
                user.favorite_restaurants = serialized_favorites
                update_fields.add('favorite_restaurants')

        for attr in ('preferences', 'survey_responses', 'fcm_token'):
            if attr in data:
                value = data.get(attr)
                if value == '':
                    value = None
                if value != getattr(user, attr):
                    setattr(user, attr, value)
                    update_fields.add(attr)

        if update_fields:
            update_fields = set(update_fields)
            update_fields.add('updated_at')
            user.save(update_fields=list(update_fields))

            sync_fields = {}
            for field in ('type_code', 'favorite_restaurants', 'fcm_token'):
                if field in update_fields:
                    sync_fields[field] = getattr(user, field)

            if sync_fields:
                guest_update_fields = list(sync_fields.keys()) + ['updated_at']
                for guest in GuestUser.objects.filter(linked_user=user):
                    for field_name, value in sync_fields.items():
                        setattr(guest, field_name, value)
                    guest.save(update_fields=guest_update_fields)
        return Response(_serialize_user(user), status=status.HTTP_200_OK)

    def put(self, request):
        return self.patch(request)
