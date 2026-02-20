import json
import requests
from django.conf import settings
from django.db import router
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
from coupons.service import issue_signup_coupon
from .utils import merge_guest_data

logger = logging.getLogger(__name__)

KAKAO_USERINFO_TIMEOUT_SECONDS = float(os.getenv("KAKAO_USERINFO_TIMEOUT_SECONDS", "10"))
AUTH_ISSUE_SIGNUP_COUPON_ON_LOGIN = os.getenv("AUTH_ISSUE_SIGNUP_COUPON_ON_LOGIN", "1") in ("1", "true", "True")


def _parse_json_safely(response):
    try:
        return response.json() or {}
    except ValueError:
        return {}


def _is_kakao_token_expired_response(response):
    """Kakao non-200 응답 중 만료/무효 토큰 케이스를 식별한다."""
    if response.status_code not in (400, 401):
        return False

    payload = _parse_json_safely(response)
    raw_code = payload.get("code")
    raw_error = payload.get("error")
    raw_msg = payload.get("msg") or payload.get("message") or payload.get("error_description")

    text_parts = [
        str(raw_code or "").lower(),
        str(raw_error or "").lower(),
        str(raw_msg or "").lower(),
        (response.text or "")[:300].lower(),
    ]
    joined = " ".join(text_parts)
    return any(keyword in joined for keyword in ("expired", "invalid token", "token", "만료", "-401"))


def _log_kakao_non_200(user_agent, client_ip, response, is_token_expired):
    """
    카카오 비정상 응답 로그를 샘플링한다.
    - 만료/무효 토큰은 info 레벨(노이즈 완화)
    - 그 외는 warning 레벨 유지
    """
    kind = "token" if is_token_expired else "error"
    cache_key = f"kakao_login_non200:{kind}:{response.status_code}:{client_ip}"
    if not cache.add(cache_key, "1", timeout=60):
        return

    log_msg = (
        f"Kakao API non-200 ({'token_expired_or_invalid' if is_token_expired else 'unexpected'}) "
        f"status={response.status_code} - User-Agent: {user_agent}, "
        f"Response: {(response.text or '')[:200]}"
    )
    if is_token_expired:
        logger.info(log_msg)
    else:
        logger.warning(log_msg)


def _mint_tokens_with_expiry(user):
    tokens = generate_tokens_for_user(user)
    refresh = RefreshToken(tokens["refresh"])
    access_token_obj = refresh.access_token
    tokens["access_expires_at"] = access_token_obj["exp"]
    tokens["refresh_expires_at"] = refresh["exp"]
    return tokens


def _resolve_user_from_refresh_token(refresh_token: str):
    refresh_obj = RefreshToken(refresh_token)
    user_id = refresh_obj.get("user_id")
    if not user_id:
        raise TokenError("token_missing_user_id")

    user_db_alias = router.db_for_read(User)
    user = User.objects.using(user_db_alias).filter(id=user_id).first()
    if user is None:
        raise TokenError("token_user_not_found")

    return refresh_obj, user, user_id, user_db_alias


def _parse_favorite_restaurants(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (TypeError, json.JSONDecodeError):
            return []
    return []


def _serialize_user(user: User):
    favorites_payload = _parse_favorite_restaurants(user.favorite_restaurants)

    return {
        'id': user.id,
        'kakao_id': user.kakao_id,
        'nickname': user.nickname,
        'student_id': user.student_id,
        'department': user.department,
        'school': user.school,
        'type_code': user.type_code,
        'favorite_restaurants': favorites_payload,
        'fcm_token': user.fcm_token,
        'preferences': user.preferences,
        'survey_responses': user.survey_responses,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
    }


def _save_user_favorites(user: User, favorites):
    serialized = json.dumps(favorites)
    if serialized == user.favorite_restaurants:
        return

    user.favorite_restaurants = serialized
    user.save(update_fields=["favorite_restaurants", "updated_at"])

    for guest in GuestUser.objects.filter(linked_user=user):
        guest.favorite_restaurants = serialized
        guest.save(update_fields=["favorite_restaurants", "updated_at"])


class UserFavoritesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = _parse_favorite_restaurants(request.user.favorite_restaurants)
        return Response({"ok": True, "favorites": favorites}, status=status.HTTP_200_OK)

    def post(self, request):
        restaurant_id = request.data.get("restaurantId") or request.data.get("restaurant_id")
        if not restaurant_id:
            return Response({"detail": "restaurantId is required"}, status=status.HTTP_400_BAD_REQUEST)

        restaurant_id = str(restaurant_id).strip()
        if not restaurant_id:
            return Response({"detail": "restaurantId is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        favorites = _parse_favorite_restaurants(user.favorite_restaurants)
        if restaurant_id not in favorites:
            favorites.append(restaurant_id)
            _save_user_favorites(user, favorites)

        return Response(
            {"ok": True, "added": restaurant_id, "favorites": favorites},
            status=status.HTTP_200_OK,
        )


class UserFavoriteDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, restaurant_id):
        restaurant_id = str(restaurant_id).strip()
        if not restaurant_id:
            return Response({"detail": "restaurantId is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        favorites = _parse_favorite_restaurants(user.favorite_restaurants)
        if restaurant_id in favorites:
            favorites = [fav for fav in favorites if fav != restaurant_id]
            _save_user_favorites(user, favorites)

        return Response(
            {"ok": True, "removed": restaurant_id, "favorites": favorites},
            status=status.HTTP_200_OK,
        )


class KakaoLoginView(APIView):
    # Kakao 로그인은 로그인 전 엔드포인트이므로 JWT 인증 비적용
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # 요청 스펙: JSON body로 refresh(선택), access_token(선택), guest_uuid(선택)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
        try:
            refresh_token = request.data.get('refresh') or request.data.get('refresh_token')
            access_token = request.data.get('access_token') or request.data.get('accessToken')
            guest_uuid = request.data.get('guest_uuid')
            
            logger.info(
                f'Login attempt - User-Agent: {user_agent}, IP: {client_ip}, '
                f'Has kakao_access_token: {bool(access_token)}, Has refresh_token: {bool(refresh_token)}'
            )

            # 0) 우리 refresh token이 있으면 카카오 검증보다 우선 처리
            if refresh_token:
                try:
                    refresh_obj, user, _, _ = _resolve_user_from_refresh_token(refresh_token)
                    tokens = _mint_tokens_with_expiry(user)

                    resp = {
                        'token': tokens,
                        'user': {
                            'id': user.id,
                            'kakao_id': user.kakao_id,
                            'nickname': user.nickname or '',
                            'profile_image_url': '',
                        },
                        'is_new': False,
                        'auth_method': 'refresh',
                    }
                    logger.info(
                        f'Refresh-first login successful - User-Agent: {user_agent}, '
                        f'IP: {client_ip}, User ID: {user.id}'
                    )
                    return Response(resp, status=status.HTTP_200_OK)
                except TokenError as exc:
                    logger.info(
                        f'Refresh-first login unavailable (invalid/expired refresh): '
                        f'User-Agent: {user_agent}, IP: {client_ip}, Error: {str(exc)}'
                    )
                except Exception as exc:
                    logger.warning(
                        f'Refresh-first login failed unexpectedly - User-Agent: {user_agent}, '
                        f'IP: {client_ip}, Error: {str(exc)}',
                        exc_info=True,
                    )

            if not access_token:
                logger.warning(f'Login failed: access_token and refresh missing - User-Agent: {user_agent}')
                return Response(
                    {'detail': 'access_token or refresh is required', 'code': 'invalid_request'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 1) Kakao 프로필 조회
            try:
                kakao_response = requests.get(
                    'https://kapi.kakao.com/v2/user/me',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=KAKAO_USERINFO_TIMEOUT_SECONDS,
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
                is_token_expired = _is_kakao_token_expired_response(kakao_response)
                _log_kakao_non_200(
                    user_agent=user_agent,
                    client_ip=client_ip,
                    response=kakao_response,
                    is_token_expired=is_token_expired,
                )
                return Response(
                    {
                        'detail': 'kakao_token_invalid',
                        'code': 'kakao_token_expired' if is_token_expired else f'http_{kakao_response.status_code}',
                        'relogin_required': True if is_token_expired else False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )

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
            if created and AUTH_ISSUE_SIGNUP_COUPON_ON_LOGIN:
                try:
                    coupon = issue_signup_coupon(user)
                    signup_coupon_code = coupon.code
                except Exception as exc:
                    logger.warning(
                        "failed to issue signup coupon for user %s: %s",
                        user.id,
                        exc,
                    )

            # 3) JWT 발급
            try:
                tokens = _mint_tokens_with_expiry(user)
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
            refresh, user, user_id, user_db_alias = _resolve_user_from_refresh_token(refresh_token)
            
            # ROTATE_REFRESH_TOKENS가 True일 때, 새로운 refresh token 생성
            # BaseTokenRefreshView의 로직을 따름
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # 기존 refresh token을 blacklist에 추가
                refresh.blacklist()
                # 새로운 refresh token 생성
                new_refresh = RefreshToken.for_user(user)
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

            # 캐시에 저장 (5초 동안 유효) - 동시 요청 방지
            cache.set(cache_key, response_data, timeout=5)

            logger.info("Token refreshed successfully for user %s (db=%s)", user_id, user_db_alias)
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
        """
        프로필 일부 또는 전체 수정. 닉네임/학번/학과/학교는 한 번에 보내도 되고, 필요한 것만 보내도 됨.
        """
        user = request.user
        data = request.data or {}
        update_fields = set()

        for attr, max_len in (('nickname', 50), ('student_id', 20), ('department', 100), ('school', 100)):
            if attr not in data:
                continue
            value = data.get(attr)
            if value is not None and value != '':
                value = str(value).strip()
                if max_len and len(value) > max_len:
                    return Response(
                        {'detail': f'{attr} must be at most {max_len} characters'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                value = None
            if getattr(user, attr) != value:
                setattr(user, attr, value)
                update_fields.add(attr)

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
