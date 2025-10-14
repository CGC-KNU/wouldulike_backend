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


def send_notification(tokens: Iterable[str], message: str):
    """
    Send push notification via FCM HTTP v1 to the given tokens.

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

    successes = []
    failures = []

    for token in tokens:
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

    return {
        "success": len(successes),
        "failure": len(failures),
        "succeeded_tokens": successes,
        "failed_tokens": failures,
    }
