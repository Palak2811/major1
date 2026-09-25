"""Redis fixed-window rate limiter.

Phase 1: wired into auth routes but disabled unless RATE_LIMIT_ENABLED=true.
Phase 5 turns it on everywhere with per-user + per-endpoint keys.
"""

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_redis = None


def _client():
    global _redis
    if _redis is None:
        import redis.asyncio as redis

        _redis = redis.from_url(get_settings().redis_url)
    return _redis


def rate_limit(limit: int, window_seconds: int, name: str):
    async def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled or not get_settings().redis_url:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{name}:{ip}"
        try:
            r = _client()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window_seconds)
        except Exception:
            return  # fail open if Redis is down; never lock users out due to infra
        if count > limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")

    return dependency
