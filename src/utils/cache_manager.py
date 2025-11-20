"""
Caching layer for RAG responses.
Uses in-memory caching with optional Redis support.
"""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps
import time
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """In-memory cache manager with TTL support."""
    
    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 3600):
        """
        Initialize cache manager.
        
        Args:
            max_size: Maximum number of entries to cache
            default_ttl_seconds: Default time-to-live for cache entries (1 hour)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, query: str, filters: Optional[Dict] = None) -> str:
        """Generate cache key from query and filters."""
        cache_input = json.dumps({
            "query": query,
            "filters": filters or {}
        }, sort_keys=True)
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def get(self, query: str, filters: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached response.
        
        Args:
            query: User query
            filters: Query filters
        
        Returns:
            Cached response or None if not found/expired
        """
        key = self._generate_key(query, filters)
        
        if key not in self.cache:
            self.misses += 1
            return None
        
        entry = self.cache[key]
        
        # Check if expired
        if datetime.utcnow() > entry['expires_at']:
            del self.cache[key]
            self.misses += 1
            logger.debug(f"Cache entry expired: {key}")
            return None
        
        self.hits += 1
        logger.debug(f"Cache hit for query: {query[:50]}...")
        return entry['data']
    
    def set(self, query: str, response: Dict[str, Any], 
            filters: Optional[Dict] = None, ttl_seconds: Optional[int] = None) -> None:
        """
        Store response in cache.
        
        Args:
            query: User query
            response: Response to cache
            filters: Query filters
            ttl_seconds: Time-to-live in seconds
        """
        # Enforce cache size limit
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        key = self._generate_key(query, filters)
        ttl = ttl_seconds or self.default_ttl
        
        self.cache[key] = {
            'data': response,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl)
        }
        
        logger.debug(f"Cached response for query: {query[:50]}... (TTL: {ttl}s)")
    
    def _evict_oldest(self) -> None:
        """Evict oldest entry when cache is full."""
        if not self.cache:
            return
        
        oldest_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k]['created_at']
        )
        del self.cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry: {oldest_key}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total
        }
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        expired_keys = [
            key for key, entry in self.cache.items()
            if datetime.utcnow() > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


# Global cache instance
_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    return _cache_manager


def cached_response(ttl_seconds: int = 3600):
    """
    Decorator to cache function responses based on query and filters.
    
    Args:
        ttl_seconds: Time-to-live for cache entries
    
    Example:
        @cached_response(ttl_seconds=1800)
        async def query_handler(query: str, filters: Optional[Dict] = None):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(query: str, filters: Optional[Dict] = None, 
                               use_cache: bool = True, *args, **kwargs):
            # Check cache first
            if use_cache:
                cached = _cache_manager.get(query, filters)
                if cached is not None:
                    cached['cache_hit'] = True
                    return cached
            
            # Call original function
            result = await func(query, filters, *args, **kwargs)
            
            # Store in cache
            _cache_manager.set(query, result, filters, ttl_seconds)
            result['cache_hit'] = False
            
            return result
        
        @wraps(func)
        def sync_wrapper(query: str, filters: Optional[Dict] = None, 
                        use_cache: bool = True, *args, **kwargs):
            # Check cache first
            if use_cache:
                cached = _cache_manager.get(query, filters)
                if cached is not None:
                    cached['cache_hit'] = True
                    return cached
            
            # Call original function
            result = func(query, filters, *args, **kwargs)
            
            # Store in cache
            _cache_manager.set(query, result, filters, ttl_seconds)
            result['cache_hit'] = False
            
            return result
        
        # Return appropriate wrapper
        if hasattr(func, '__await__'):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RedisCacheManager:
    """
    Redis-based cache manager for distributed caching.
    Optional: Use only if Redis is available.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 default_ttl_seconds: int = 3600):
        """Initialize Redis cache manager."""
        try:
            import redis
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.default_ttl = default_ttl_seconds
            self.available = True
            logger.info(f"Redis cache initialized: {redis_url}")
        except ImportError:
            logger.warning("Redis not installed. Falling back to in-memory cache.")
            self.available = False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
            self.available = False
    
    def _generate_key(self, query: str, filters: Optional[Dict] = None) -> str:
        """Generate cache key from query and filters."""
        cache_input = json.dumps({
            "query": query,
            "filters": filters or {}
        }, sort_keys=True)
        return f"rag_cache:{hashlib.md5(cache_input.encode()).hexdigest()}"
    
    def get(self, query: str, filters: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Retrieve cached response from Redis."""
        if not self.available:
            return None
        
        try:
            key = self._generate_key(query, filters)
            cached = self.redis_client.get(key)
            
            if cached:
                logger.debug(f"Redis cache hit for query: {query[:50]}...")
                return json.loads(cached)
            
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set(self, query: str, response: Dict[str, Any], 
            filters: Optional[Dict] = None, ttl_seconds: Optional[int] = None) -> None:
        """Store response in Redis."""
        if not self.available:
            return
        
        try:
            key = self._generate_key(query, filters)
            ttl = ttl_seconds or self.default_ttl
            self.redis_client.setex(key, ttl, json.dumps(response))
            logger.debug(f"Cached in Redis for query: {query[:50]}... (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        if not self.available:
            return
        
        try:
            self.redis_client.delete(*self.redis_client.keys("rag_cache:*"))
            logger.info("Redis cache cleared")
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
