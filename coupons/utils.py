import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator, Optional

from django.core.cache import cache

try:
    import ulid  # provided by the 'ulid-py' package
except Exception as e:  # pragma: no cover
    ulid = None  # type: ignore


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

    - Acquires a lock with SET NX EX.
    - Spins until acquired or `max_wait` elapses.
    - Releases lock only if token matches (best-effort).

    Args:
        key: Lock key name.
        ttl: Expiration for the lock in seconds.
        spin: Sleep seconds between attempts.
        max_wait: Total wait budget before timing out.
    """
    token = str(uuid.uuid4())
    deadline = time.time() + max_wait
    acquired = False

    # Get raw redis client (requires django-redis backend)
    client = cache.client.get_client(False)  # type: ignore[attr-defined]

    while time.time() < deadline:
        acquired = client.set(name=key, value=token, nx=True, ex=ttl)
        if acquired:
            break
        time.sleep(spin)

    try:
        if not acquired:
            raise TimeoutError("lock timeout")
        yield
    finally:
        try:
            # Release only if we still own the lock
            val: Optional[bytes] = client.get(key)
            if val and (val.decode() == token):
                client.delete(key)
        except Exception:
            # best-effort unlock; ignore errors
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
