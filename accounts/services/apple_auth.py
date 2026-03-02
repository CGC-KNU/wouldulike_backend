"""
Apple Sign In identity_token 검증 서비스.

- Apple JWKS(https://appleid.apple.com/auth/keys)를 캐싱하여 매 요청마다 fetch하지 않음
- identity_token의 signature, iss, aud, exp 검증
"""

import json
import logging
from typing import Any

import jwt
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_CACHE_KEY = "apple_jwks"
APPLE_JWKS_CACHE_TIMEOUT = 3600  # 1시간


def _fetch_jwks_uncached() -> dict:
    """Apple JWKS를 fetch (캐시 무시)"""
    try:
        resp = requests.get(APPLE_JWKS_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch Apple JWKS: %s", e)
        raise


def _get_jwks() -> dict:
    """캐시된 Apple JWKS 반환 (1시간 TTL)"""
    jwks = cache.get(APPLE_JWKS_CACHE_KEY)
    if jwks is not None:
        return jwks
    jwks = _fetch_jwks_uncached()
    cache.set(APPLE_JWKS_CACHE_KEY, jwks, timeout=APPLE_JWKS_CACHE_TIMEOUT)
    return jwks


def _get_signing_key(header: dict) -> Any:
    """토큰 헤더의 kid에 해당하는 공개키 반환"""
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    jwks = _get_jwks()
    keys = jwks.get("keys") or []
    for key_data in keys:
        if key_data.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

    raise ValueError(f"No matching key found for kid={kid}")


def verify_identity_token(
    identity_token: str,
    *,
    audience: str | None = None,
) -> dict:
    """
    Apple identity_token(JWT)을 검증하고 claims를 반환한다.

    Args:
        identity_token: Apple에서 발급한 JWT identity token
        audience: 기대하는 aud (APPLE_AUDIENCE). None이면 settings에서 읽음

    Returns:
        검증된 JWT payload (sub, email, email_verified 등)

    Raises:
        jwt.InvalidTokenError: 토큰이 유효하지 않을 때
        ValueError: kid 누락, 키 미발견 등
    """
    aud = audience or getattr(settings, "APPLE_AUDIENCE", None)
    if not aud:
        raise ValueError("APPLE_AUDIENCE is required for Apple token verification")
    # 리스트면 PyJWT에 그대로 전달 (여러 audience 허용)
    if isinstance(aud, str):
        aud = [aud] if aud else None

    # 헤더에서 kid 추출 (서명 검증 전)
    try:
        header = jwt.get_unverified_header(identity_token)
    except jwt.DecodeError as e:
        logger.warning("Apple identity_token decode error: %s", e)
        raise
    signing_key = _get_signing_key(header)

    # audience는 문자열 또는 리스트일 수 있음 (Apple은 서비스 ID 또는 Bundle ID)
    decoded = jwt.decode(
        identity_token,
        signing_key,
        algorithms=["RS256"],
        audience=aud,
        issuer=APPLE_ISSUER,
        options={
            "verify_signature": True,
            "verify_exp": True,
            "verify_aud": True,
            "verify_iss": True,
        },
    )
    return decoded
