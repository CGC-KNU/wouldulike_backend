import json
import logging
import os
from typing import Iterable, Optional, Tuple, List, Dict

from django.conf import settings
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

# 여러 프로젝트 세션 캐시
_project_sessions_cache: Dict[str, Tuple[AuthorizedSession, str]] = {}


def _load_service_account_credentials(service_account_file=None, service_account_json=None):
    """
    Build Google service account credentials for FCM HTTP v1.

    Supports loading from:
      * service_account_json (raw JSON string)
      * service_account_file (path to JSON)
    """
    if service_account_json:
        try:
            info = json.loads(service_account_json) if isinstance(service_account_json, str) else service_account_json
        except json.JSONDecodeError:
            logger.exception("FCM service account JSON could not be decoded")
            return None
        return service_account.Credentials.from_service_account_info(
            info,
            scopes=[_FCM_SCOPE],
        )

    if service_account_file:
        try:
            return service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=[_FCM_SCOPE],
            )
        except FileNotFoundError:
            logger.exception(
                "FCM service account file not found at %s", service_account_file
            )
        except Exception:
            logger.exception("Failed to load FCM service account credentials")
    
    return None


def _build_authorized_session(project_id=None, service_account_file=None, service_account_json=None) -> Optional[Tuple[AuthorizedSession, str]]:
    """
    Build authorized session for a specific project.
    If project_id is None, uses default settings.
    """
    # 캐시 확인
    cache_key = project_id or "default"
    if cache_key in _project_sessions_cache:
        return _project_sessions_cache[cache_key]
    
    # 기본 설정 사용 (하위 호환성)
    if project_id is None and service_account_file is None and service_account_json is None:
        service_account_json = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
        service_account_file = getattr(settings, "FCM_SERVICE_ACCOUNT_FILE", None) or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
    
    credentials = _load_service_account_credentials(service_account_file, service_account_json)
    if not credentials:
        return None

    resolved_project_id = project_id or getattr(settings, "FCM_PROJECT_ID", None) or getattr(
        credentials, "project_id", None
    )
    if not resolved_project_id:
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

    session = AuthorizedSession(credentials)
    result = (session, resolved_project_id)
    _project_sessions_cache[cache_key] = result
    return result


def _get_all_fcm_projects() -> List[Tuple[AuthorizedSession, str]]:
    """
    Get all configured FCM project sessions.
    Supports multiple projects via FCM_PROJECT_CONFIGS environment variable.
    Format: JSON string with list of project configs.
    Example: [{"project_id": "project1", "service_account_file": "/path/to/file1.json"}, ...]
    """
    sessions = []
    
    # 여러 프로젝트 설정 확인
    project_configs = getattr(settings, "FCM_PROJECT_CONFIGS", None)
    if project_configs:
        try:
            if isinstance(project_configs, str):
                configs = json.loads(project_configs)
            else:
                configs = project_configs
            
            for config in configs:
                project_id = config.get("project_id")
                service_account_file = config.get("service_account_file")
                service_account_json = config.get("service_account_json")
                
                session = _build_authorized_session(
                    project_id=project_id,
                    service_account_file=service_account_file,
                    service_account_json=service_account_json
                )
                if session:
                    sessions.append(session)
                    logger.info(f"Loaded FCM project: {session[1]}")
        except Exception as e:
            logger.exception(f"Failed to load FCM project configs: {e}")
    
    # 기본 프로젝트 추가 (하위 호환성)
    default_session = _build_authorized_session()
    if default_session:
        # 중복 체크
        if not any(s[1] == default_session[1] for s in sessions):
            sessions.append(default_session)
    
    return sessions


def send_notification(tokens: Iterable[str], message: str):
    """
    Send push notification via FCM HTTP v1 to the given tokens.
    Automatically tries multiple Firebase projects if SENDER_ID_MISMATCH occurs.

    Returns a dict containing success/failure counts and details, or None when
    no request was sent.
    """
    tokens = [token for token in tokens if token]
    if not tokens:
        logger.debug("Skipping FCM send: no tokens provided")
        return None

    # 모든 프로젝트 세션 가져오기
    project_sessions = _get_all_fcm_projects()
    if not project_sessions:
        logger.warning("Skipping FCM send: could not build authorized session")
        return None

    successes = []
    failures = []
    remaining_tokens = list(tokens)

    # 각 프로젝트로 전송 시도
    for session, project_id in project_sessions:
        if not remaining_tokens:
            break
        
        endpoint = _FCM_ENDPOINT.format(project_id=project_id)
        project_successes = []
        project_failures = []
        
        logger.debug(f"Trying to send to {len(remaining_tokens)} tokens via project {project_id}")
        
        for token in remaining_tokens[:]:  # 복사본으로 순회
            payload = {
                "message": {
                    "token": token,
                    "notification": {"body": message},
                }
            }
            try:
                response = session.post(endpoint, json=payload, timeout=10)
            except Exception:
                logger.exception("FCM request failed for token %s", token)
                project_failures.append({
                    "token": token,
                    "error": "request_exception",
                    "project_id": project_id
                })
                continue

            if response.ok:
                project_successes.append(token)
                remaining_tokens.remove(token)  # 성공한 토큰은 제거
                continue

            try:
                error_detail = response.json()
            except ValueError:
                error_detail = {"error": response.text}

            error_code = ""
            error_status = error_detail.get("error", {}).get("status", "")
            
            # 에러 상세 정보 추출
            for detail in error_detail.get("error", {}).get("details", []):
                if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
                    error_code = detail.get("errorCode", "")
                    break

            # SENDER_ID_MISMATCH인 경우 다음 프로젝트로 시도할 수 있도록 유지
            if error_code == "SENDER_ID_MISMATCH":
                logger.debug(
                    f"Token {token[:20]}... failed with SENDER_ID_MISMATCH for project {project_id}, "
                    "will try next project"
                )
                # 다음 프로젝트로 시도하기 위해 remaining_tokens에 유지
                continue
            else:
                # 다른 에러는 실패로 기록하고 제거
                project_failures.append({
                    "token": token,
                    "status_code": response.status_code,
                    "response": error_detail,
                    "project_id": project_id,
                    "error_code": error_code,
                })
                remaining_tokens.remove(token)
                logger.warning(
                    f"FCM send failed for token {token[:20]}... via project {project_id}: {error_detail}"
                )

        successes.extend(project_successes)
        failures.extend(project_failures)
        
        if project_successes:
            logger.info(f"Successfully sent {len(project_successes)} notifications via project {project_id}")

    # 모든 프로젝트를 시도했는데도 남은 토큰들은 실패로 기록
    for token in remaining_tokens:
        failures.append({
            "token": token,
            "error": "SENDER_ID_MISMATCH for all projects",
            "status": "FAILED_ALL_PROJECTS"
        })
        logger.warning(
            f"Token {token[:20]}... failed for all configured projects"
        )

    return {
        "success": len(successes),
        "failure": len(failures),
        "succeeded_tokens": successes,
        "failed_tokens": failures,
    }
