import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator, Optional

from django.core.cache import cache

try:
    import ulid  # provided by the 'ulid-py' package
except Exception as e:  # pragma: no cover
    ulid = None  # type: ignore

logger = logging.getLogger(__name__)


def make_coupon_code(length: int = 12) -> str:
    """Generate a short unique coupon code.

    Uses ULID (time-ordered, 26 chars) and truncates to the requested length
    for readability while keeping sufficient entropy for most use cases.

    Args:
        length: Desired code length (between 6 and 26).

    Returns:
        A base32 Crockford-encoded string, uppercase, URL-safe.
    """
    if length < 6:
        length = 6
    if length > 26:
        length = 26
    if ulid is None:
        # Fallback: uuid4 (remove dashes, take prefix)
        return uuid.uuid4().hex[:length].upper()
    return ulid.new().str[:length]


@contextmanager
def redis_lock(
    key: str,
    ttl: int = 5,
    spin: float = 0.02,
    max_wait: float = 2.0,
) -> Generator[None, None, None]:
    """A simple Redis spin-lock using django-redis low-level client.

    Falls back to a no-op lock when Redis is unavailable so development
    environments without Redis do not raise 500 errors.
    """
    token = str(uuid.uuid4())
    deadline = time.time() + max_wait
    acquired = False

    try:
        client = cache.client.get_client(False)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - cache backend missing
        logger.warning("redis lock disabled: %s", exc)
        client = None

    if client is None:
        yield
        return

    while time.time() < deadline:
        try:
            acquired = client.set(name=key, value=token, nx=True, ex=ttl)
        except Exception as exc:
            logger.warning("redis lock fell back to noop: %s", exc)
            client = None
            break
        if acquired:
            break
        time.sleep(spin)

    if client is None:
        yield
        return

    try:
        if not acquired:
            raise TimeoutError("lock timeout")
        yield
    finally:
        try:
            val: Optional[bytes] = client.get(key)
            if val and (val.decode() == token):
                client.delete(key)
        except Exception:
            pass


def idem_get(key: str) -> Any:
    """Get idempotency value from cache."""
    return cache.get(key)


def idem_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set idempotency value in cache with TTL (seconds)."""
    cache.set(key, value, ttl)


__all__ = [
    "make_coupon_code",
    "redis_lock",
    "idem_get",
    "idem_set",
]
