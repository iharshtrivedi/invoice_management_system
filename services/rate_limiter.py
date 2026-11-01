from __future__ import annotations

import hashlib
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError


_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


def _client_ip(request: Request) -> str:
    """Return the direct peer address; configure proxy header handling at deployment."""
    return request.client.host if request.client else "unknown"


def rate_limit(*, limit: int, window_seconds: int, scope: str) -> Callable[[Request], object]:
    """Create a Redis-backed, per-IP fixed-window FastAPI dependency."""

    async def enforce(request: Request) -> None:
        client_hash = hashlib.sha256(_client_ip(request).encode()).hexdigest()
        key = f"rate-limit:auth:{scope}:{client_hash}"
        redis: Redis = request.app.state.redis

        try:
            count, ttl = await redis.eval(_INCREMENT_WITH_EXPIRY, 1, key, window_seconds)
        except RedisError as exc:
            # Authentication endpoints must not become unthrottled if Redis is unavailable.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service unavailable",
            ) from exc

        if int(count) > limit:
            retry_after = max(int(ttl), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return enforce
