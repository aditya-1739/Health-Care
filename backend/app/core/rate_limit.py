import logging
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional
from fastapi import HTTPException, Request, status
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Atomic Redis Lua script for safe concurrent rate limiting
_REDIS_LUA_RATELIMIT = """
local current = redis.call('INCR', KEYS[1])
if tonumber(current) == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""

# In-memory sliding window rate limiter (for local development & unit test fallback only)
_in_memory_requests: Dict[str, List[float]] = defaultdict(list)
_redis_client: Optional[redis.Redis] = None
_redis_checked = False


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client, _redis_checked
    if not _redis_checked:
        try:
            client = redis.from_url(settings.REDIS_URL, socket_timeout=0.1)
            client.ping()
            _redis_client = client
        except Exception:
            _redis_client = None
        _redis_checked = True
    return _redis_client


def reset_rate_limiter_state():
    """Reset rate limiter state (useful for tests)."""
    global _in_memory_requests
    _in_memory_requests.clear()
    r_client = get_redis_client()
    if r_client is not None:
        try:
            rl_keys = r_client.keys("rl:*")
            if rl_keys:
                r_client.delete(*rl_keys)
        except Exception:
            pass


def rate_limiter(action: str, max_requests: int, window_seconds: int = 60) -> Callable:
    """
    FastAPI dependency for endpoint rate limiting.
    
    Guarantees:
    - Uses atomic Redis Lua script under concurrent production traffic.
    - Dimensions: Action + Client IP / Authenticated User ID.
    - Gracefully falls back to in-memory window during local development / testing.
    """
    async def dependency(request: Request):
        # Extract client identifier: IP or authorization header prefix
        client_ip = request.client.host if request.client else "unknown_ip"
        auth_header = request.headers.get("Authorization", "")
        identifier = auth_header[:20] if auth_header else client_ip
        key = f"rl:{action}:{identifier}"

        r_client = get_redis_client()

        if r_client is not None:
            try:
                # Atomic execution in Redis
                script = r_client.register_script(_REDIS_LUA_RATELIMIT)
                current_count = script(keys=[key], args=[window_seconds])
                if int(current_count) > max_requests:
                    ttl = r_client.ttl(key)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests. Please try again later.",
                        headers={"Retry-After": str(max(1, ttl))},
                    )
                return
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Redis rate limiter failed ({e}). Falling back to in-process limiter.")

        # In-memory fallback (Development / Test environments)
        now = time.time()
        timestamps = _in_memory_requests[key]
        # Purge expired timestamps outside the window
        valid_timestamps = [t for t in timestamps if t > now - window_seconds]
        _in_memory_requests[key] = valid_timestamps

        if len(valid_timestamps) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

        _in_memory_requests[key].append(now)

    return dependency
