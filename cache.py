"""
cache.py — Layer 2 Exact-Match Response Cache (Redis with In-Memory Fallback)
"""
import hashlib
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)
_IN_MEMORY_CACHE = {}

try:
    import redis
    redis_client = redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=1.0
    )
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False

def _hash_query(query: str) -> str:
    """Hash query string with SHA256 for key lookup."""
    return f"rag:cache:{hashlib.sha256(query.strip().lower().encode('utf-8')).hexdigest()}"

def get_cached_response(query: str) -> Optional[str]:
    """Layer 2 Cache Read: Redis -> In-Memory Fallback."""
    if not query:
        return None
    key = _hash_query(query)
    if REDIS_AVAILABLE and redis_client:
        try:
            val = redis_client.get(key)
            if val:
                return val
        except Exception:
            pass
    return _IN_MEMORY_CACHE.get(key)

def set_cached_response(query: str, response: str, ttl_seconds: int = 3600) -> None:
    """Layer 2 Cache Write: Store response with TTL."""
    if not query or not response:
        return
    key = _hash_query(query)
    if REDIS_AVAILABLE and redis_client:
        try:
            redis_client.setex(key, ttl_seconds, response)
            return
        except Exception:
            pass
    _IN_MEMORY_CACHE[key] = response