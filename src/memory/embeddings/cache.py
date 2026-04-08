"""Cached embedding provider with LRU cache for frequent queries."""

import hashlib
import time
from collections import OrderedDict
from typing import Optional

from memory.embeddings.base import EmbeddingProvider


class CachedEmbeddingProvider(EmbeddingProvider):
    """LRU cache wrapper for embedding providers.
    
    Reduces latency from ~200ms to ~5ms for repeated queries.
    """
    
    def __init__(
        self,
        provider: EmbeddingProvider,
        maxsize: int = 1000,
        ttl_seconds: Optional[int] = None,
    ):
        """Initialize cached provider.
        
        Args:
            provider: Underlying embedding provider
            maxsize: Maximum cache size (LRU eviction)
            ttl_seconds: Optional TTL for cache entries
        """
        self.provider = provider
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[list[float], Optional[int]]] = OrderedDict()
    
    def _key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    
    def embed(self, text: str) -> list[float]:
        """Get embedding with caching."""
        key = self._key(text)
        now = int(time.time())
        
        # Check cache
        if key in self._cache:
            embedding, expires = self._cache[key]
            
            # Check TTL
            if expires is None or now < expires:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return embedding
            
            # Expired, remove
            del self._cache[key]
        
        # Get from provider
        embedding = self.provider.embed(text)
        
        # Store in cache
        expires = now + self.ttl_seconds if self.ttl_seconds else None
        self._cache[key] = (embedding, expires)
        self._cache.move_to_end(key)
        
        # Evict if over limit
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)
        
        return embedding
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding with per-item caching."""
        return [self.embed(t) for t in texts]
    
    def cache_info(self) -> dict:
        """Get cache statistics."""
        now = int(time.time())
        expired = sum(1 for _, exp in self._cache.values() if exp and now >= exp)
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "expired": expired,
            "ttl_seconds": self.ttl_seconds,
        }
    
    def cache_clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
