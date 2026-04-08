"""Tests for cached embedding provider."""

import time
import pytest
from memory.embeddings.cache import CachedEmbeddingProvider
from memory.embeddings.base import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock provider for testing."""
    
    def __init__(self, latency: float = 0.01):
        self.call_count = 0
        self.latency = latency
    
    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        time.sleep(self.latency)
        # Simple deterministic embedding based on text
        hash_val = hash(text) % 1000
        return [float(hash_val + i) / 1000.0 for i in range(10)]


class TestCachedEmbeddingProvider:
    
    def test_caches_repeated_queries(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        # First call hits provider
        r1 = cached.embed("test text")
        assert mock.call_count == 1
        
        # Second call hits cache
        r2 = cached.embed("test text")
        assert mock.call_count == 1  # No new call
        assert r1 == r2
    
    def test_different_texts_different_cache_entries(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        cached.embed("text A")
        cached.embed("text B")
        
        assert mock.call_count == 2
    
    def test_lru_eviction(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=2)
        
        # Fill cache
        cached.embed("A")
        cached.embed("B")
        assert mock.call_count == 2
        
        # Access A (makes it most recent)
        cached.embed("A")
        assert mock.call_count == 2  # Still cached
        
        # Add C, should evict B (least recent)
        cached.embed("C")
        assert mock.call_count == 3
        
        # A should still be cached
        cached.embed("A")
        assert mock.call_count == 3  # Still cached
        
        # B should require new call
        cached.embed("B")
        assert mock.call_count == 4
    
    def test_ttl_expiration(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100, ttl_seconds=0)
        
        cached.embed("test")
        assert mock.call_count == 1
        
        # Should be expired immediately
        time.sleep(0.1)
        cached.embed("test")
        assert mock.call_count == 2
    
    def test_cache_info(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        cached.embed("A")
        cached.embed("B")
        
        info = cached.cache_info()
        assert info["size"] == 2
        assert info["maxsize"] == 100
        assert info["ttl_seconds"] is None
    
    def test_cache_clear(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        cached.embed("test")
        assert cached.cache_info()["size"] == 1
        
        cached.cache_clear()
        assert cached.cache_info()["size"] == 0
    
    def test_embed_batch_uses_cache(self):
        mock = MockEmbeddingProvider()
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        # Batch call
        results = cached.embed_batch(["A", "B", "A"])
        assert mock.call_count == 2  # A and B, second A from cache
        assert len(results) == 3
        assert results[0] == results[2]  # Same embedding for A


class TestLatencyReduction:
    """Verify latency improvement from caching."""
    
    def test_repeated_query_faster(self):
        mock = MockEmbeddingProvider(latency=0.05)  # 50ms simulated latency
        cached = CachedEmbeddingProvider(mock, maxsize=100)
        
        # First call (cold cache)
        t1_start = time.time()
        cached.embed("latency test")
        t1_duration = time.time() - t1_start
        
        # Second call (warm cache)
        t2_start = time.time()
        cached.embed("latency test")
        t2_duration = time.time() - t2_start
        
        # Cached call should be much faster
        assert t2_duration < t1_duration / 10
        assert t2_duration < 0.005  # Under 5ms
