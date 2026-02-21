import logging
import time
import uuid


logger = logging.getLogger(__name__)


class RequestLifecycleLoggingMiddleware:
    """
    Log request start/end so hung endpoints can be identified even without access logs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = uuid.uuid4().hex[:10]
        started_at = time.perf_counter()
        request._request_id = request_id

        logger.info(
            "[req:%s] START %s %s",
            request_id,
            request.method,
            request.get_full_path(),
        )

        response = self.get_response(request)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        level = logging.WARNING if elapsed_ms >= 5000 else logging.INFO
        logger.log(
            level,
            "[req:%s] END %s %s status=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.get_full_path(),
            getattr(response, "status_code", "unknown"),
            elapsed_ms,
        )
        return response
