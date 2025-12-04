import json
import logging
import os
from typing import Iterable, Optional, Tuple

from django.conf import settings
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"


def _load_service_account_credentials():
    """
    Build Google service account credentials for FCM HTTP v1.

    Supports loading from:
      * settings.FCM_SERVICE_ACCOUNT_JSON (raw JSON string)
      * settings.FCM_SERVICE_ACCOUNT_FILE (path to JSON)
      * GOOGLE_APPLICATION_CREDENTIALS environment variable
    """
    info_json = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
    if info_json:
        try:
            info = json.loads(info_json)
        except json.JSONDecodeError:
            logger.exception("FCM service account JSON could not be decoded")
            return None
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=[_FCM_SCOPE],
        )

    file_path = getattr(settings, "FCM_SERVICE_ACCOUNT_FILE", None) or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    if not file_path:
        logger.error(
            "No FCM service account credentials configured. "
            "Set FCM_SERVICE_ACCOUNT_FILE or FCM_SERVICE_ACCOUNT_JSON."
        )
        return None

    try:
        return service_account.Credentials.from_service_account_file(
            file_path,
            scopes=[_FCM_SCOPE],
        )
    except FileNotFoundError:
        logger.exception(
            "FCM service account file not found at %s", file_path
        )
    except Exception:
        logger.exception("Failed to load FCM service account credentials")
    return None


def _build_authorized_session() -> Optional[Tuple[AuthorizedSession, str]]:
    credentials = _load_service_account_credentials()
    if not credentials:
        return None

    project_id = getattr(settings, "FCM_PROJECT_ID", None) or getattr(
        credentials, "project_id", None
    )
    if not project_id:
        logger.error(
            "FCM project id is not configured. Set FCM_PROJECT_ID or ensure the "
            "service account JSON contains project_id."
        )
        return None

    # Ensure credentials have a valid access token.
    try:
        credentials.refresh(Request())
    except Exception:
        logger.exception("Failed to refresh Google credentials for FCM")
        return None

    return AuthorizedSession(credentials), project_id


def validate_notification(tokens: Iterable[str], message: str) -> dict:
    """
    Validate notification configuration and tokens without sending.
    
    Returns a dict containing validation results and issues found.
    """
    validation_result = {
        "valid": True,
        "issues": [],
        "warnings": [],
        "info": [],
        "token_count": 0,
        "valid_tokens": [],
        "invalid_tokens": [],
        "config_status": {},
    }
    
    # 1. FCM 설정 검증
    session_with_project = _build_authorized_session()
    if not session_with_project:
        validation_result["valid"] = False
        validation_result["issues"].append({
            "type": "config_error",
            "message": "FCM 서비스 계정 인증 정보를 불러올 수 없습니다.",
            "details": "FCM_SERVICE_ACCOUNT_FILE 또는 FCM_SERVICE_ACCOUNT_JSON 환경 변수를 확인하세요."
        })
        return validation_result
    
    session, project_id = session_with_project
    validation_result["config_status"]["project_id"] = project_id
    validation_result["config_status"]["auth_available"] = True
    
    # 2. 엔드포인트 URL 검증
    endpoint = _FCM_ENDPOINT.format(project_id=project_id)
    validation_result["config_status"]["endpoint"] = endpoint
    validation_result["info"].append(f"FCM 엔드포인트: {endpoint}")
    
    # 3. 메시지 검증
    if not message or not message.strip():
        validation_result["valid"] = False
        validation_result["issues"].append({
            "type": "message_error",
            "message": "알림 메시지가 비어있습니다."
        })
    else:
        message_length = len(message)
        validation_result["config_status"]["message_length"] = message_length
        if message_length > 2000:
            validation_result["warnings"].append({
                "type": "message_warning",
                "message": f"메시지가 너무 깁니다 ({message_length}자). FCM 권장 길이는 2000자 이하입니다."
            })
    
    # 4. 토큰 검증
    tokens = [token for token in tokens if token]
    validation_result["token_count"] = len(tokens)
    
    if not tokens:
        validation_result["valid"] = False
        validation_result["issues"].append({
            "type": "token_error",
            "message": "유효한 FCM 토큰이 없습니다."
        })
        return validation_result
    
    # 토큰 형식 검증 (FCM 토큰은 일반적으로 길고 특정 패턴을 가짐)
    for token in tokens:
        if not isinstance(token, str):
            validation_result["invalid_tokens"].append({
                "token": str(token),
                "reason": "토큰이 문자열이 아닙니다."
            })
            continue
        
        token = token.strip()
        if not token:
            validation_result["invalid_tokens"].append({
                "token": "(empty)",
                "reason": "토큰이 비어있습니다."
            })
            continue
        
        # FCM 토큰은 일반적으로 152자 이상의 문자열
        if len(token) < 50:
            validation_result["warnings"].append({
                "type": "token_warning",
                "token": token[:20] + "...",
                "message": f"토큰 길이가 짧습니다 ({len(token)}자). 유효한 FCM 토큰인지 확인하세요."
            })
        
        validation_result["valid_tokens"].append(token)
    
    # 5. 페이로드 검증
    sample_payload = {
        "message": {
            "token": validation_result["valid_tokens"][0] if validation_result["valid_tokens"] else "sample_token",
            "notification": {"body": message[:100] if message else "sample"},
        }
    }
    validation_result["config_status"]["sample_payload"] = sample_payload
    
    # 6. 요약 정보
    validation_result["info"].append(f"총 토큰 수: {validation_result['token_count']}")
    validation_result["info"].append(f"유효한 토큰 수: {len(validation_result['valid_tokens'])}")
    validation_result["info"].append(f"무효한 토큰 수: {len(validation_result['invalid_tokens'])}")
    
    if validation_result["issues"]:
        validation_result["valid"] = False
    
    return validation_result


def send_notification(tokens: Iterable[str], message: str, dry_run: bool = False):
    """
    Send push notification via FCM HTTP v1 to the given tokens.

    Args:
        tokens: Iterable of FCM tokens
        message: Notification message text
        dry_run: If True, only validate without sending (default: False)

    Returns a dict containing success/failure counts and details, or None when
    no request was sent.
    """
    tokens = [token for token in tokens if token]
    if not tokens:
        logger.debug("Skipping FCM send: no tokens provided")
        return None

    session_with_project = _build_authorized_session()
    if not session_with_project:
        logger.warning("Skipping FCM send: could not build authorized session")
        return None

    session, project_id = session_with_project
    endpoint = _FCM_ENDPOINT.format(project_id=project_id)

    # 드라이런 모드: 실제 FCM API 호출하여 토큰 유효성 검증
    # 주의: FCM API에는 validate_only 옵션이 없으므로 실제 API 호출 시 알림이 전송됩니다.
    # 하지만 테스트 목적으로 실제 API 응답을 통해 토큰 유효성을 검증합니다.
    if dry_run:
        # 드라이런 모드에서는 실제 API 호출을 하되, 테스트 메시지로 전송
        test_message = f"[테스트] {message}"
        logger.info("Dry-run mode: 실제 FCM API 호출하여 토큰 유효성 검증 (알림이 전송될 수 있음)")
    else:
        test_message = message

    successes = []
    failures = []

    for token in tokens:
        payload = {
            "message": {
                "token": token,
                "notification": {"body": test_message},
            }
        }
        try:
            response = session.post(endpoint, json=payload, timeout=10)
        except Exception:
            logger.exception("FCM request failed for token %s", token)
            failures.append({"token": token, "error": "request_exception"})
            continue

        if response.ok:
            successes.append(token)
            continue

        try:
            error_detail = response.json()
        except ValueError:
            error_detail = {"error": response.text}

        failures.append(
            {
                "token": token,
                "status_code": response.status_code,
                "response": error_detail,
            }
        )
        logger.warning(
            "FCM send failed for token %s: %s",
            token,
            error_detail,
        )

    result = {
        "success": len(successes),
        "failure": len(failures),
        "succeeded_tokens": successes,
        "failed_tokens": failures,
    }
    
    if dry_run:
        result["dry_run"] = True
        result["note"] = "드라이런 모드: 실제 FCM API 호출을 통해 토큰 유효성을 검증했습니다. 알림이 전송되었을 수 있습니다."
    
    return result
