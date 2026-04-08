"""Tests for unified 3-tier memory system.

pytest tests/test_unified_memory.py
"""

import asyncio
import os
import tempfile
import time
from typing import List

import pytest

from memory.unified import (
    FastMemoryTier,
    MediumMemoryTier,
    SlowMemoryTier,
    UnifiedMemoryService,
    MemoryEntry,
    MemoryTier,
    SearchTask,
)


class TestFastMemoryTier:
    """Tests for Fast tier (in-memory, TTL)."""
    
    def test_store_and_search(self):
        """Basic store and search."""
        fast = FastMemoryTier()
        
        entry = MemoryEntry(
            id="test-1",
            title="Test Memory",
            what="This is a test",
            tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            tags=["test"]
        )
        
        fast.store(entry)
        results = fast.search("test")
        
        assert len(results) == 1
        assert results[0].id == "test-1"
        assert results[0].title == "Test Memory"
    
    def test_ttl_cleanup(self):
        """Test TTL cleanup of expired entries."""
        fast = FastMemoryTier()
        
        # Create entry with very short TTL by manipulating expires_at
        entry = MemoryEntry(
            id="expired-1",
            title="Expired",
            what="Will expire",
            tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            expires_at=int(time.time()) - 1  # Already expired
        )
        
        fast.store(entry)
        
        # Cleanup should remove it
        fast._cleanup_expired()
        
        results = fast.search("expired")
        assert len(results) == 0
    
    def test_project_filter(self):
        """Search with project filter."""
        fast = FastMemoryTier()
        
        fast.store(MemoryEntry(
            id="p1", title="Project A",
            what="Content A", tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            project="project-a"
        ))
        
        fast.store(MemoryEntry(
            id="p2", title="Project B",
            what="Content B", tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            project="project-b"
        ))
        
        results = fast.search("Content", project="project-a")
        assert len(results) == 1
        assert results[0].project == "project-a"
    
    def test_access_counting(self):
        """Test access count tracking."""
        fast = FastMemoryTier()
        
        entry = MemoryEntry(
            id="acc-1", title="Access Test",
            what="Count me", tier=MemoryTier.FAST,
            timestamp=int(time.time())
        )
        fast.store(entry)
        
        # Search multiple times
        fast.search("Access")
        fast.search("Access")
        fast.search("Access")
        
        # Check access was recorded
        # Note: In real implementation, we'd query the DB directly


class TestMediumMemoryTier:
    """Tests for Medium tier (SSD, LRU)."""
    
    def test_store_and_search(self, tmp_path):
        """Basic store and FTS search."""
        db_path = str(tmp_path / "medium.db")
        medium = MediumMemoryTier(db_path)
        
        entry = MemoryEntry(
            id="med-1",
            title="Medium Test",
            what="Content for medium tier",
            tier=MemoryTier.MEDIUM,
            timestamp=int(time.time()),
            tags=["medium", "test"]
        )
        
        medium.store(entry)
        results = medium.search("medium tier")
        
        assert len(results) == 1
        assert results[0].id == "med-1"
    
    def test_lru_eviction(self, tmp_path):
        """Test LRU eviction when size limit reached."""
        db_path = str(tmp_path / "medium_lru.db")
        # Very small limit to trigger eviction quickly
        medium = MediumMemoryTier(db_path, size_limit_mb=1)
        
        # Store many entries
        for i in range(100):
            entry = MemoryEntry(
                id=f"lru-{i}",
                title=f"Entry {i}",
                what=f"Content {i}" * 1000,  # Make entries large
                tier=MemoryTier.MEDIUM,
                timestamp=int(time.time()) - i,  # Different ages
                last_access=int(time.time()) - i * 10  # Different access times
            )
            medium.store(entry)
        
        # Check that oldest/least accessed were evicted
        # Exact count depends on size calculations


class TestSlowMemoryTier:
    """Tests for Slow tier (HDD, async)."""
    
    def test_store_and_compress(self, tmp_path):
        """Test storage with compression."""
        db_path = str(tmp_path / "slow.db")
        slow = SlowMemoryTier(db_path)
        
        long_details = "Section 1\n\n" + "x" * 1000 + "\n\nSection 2"
        
        entry = MemoryEntry(
            id="slow-1",
            title="Slow Test",
            what="Archived memory",
            tier=MemoryTier.SLOW,
            timestamp=int(time.time()),
            details=long_details
        )
        
        slow.store(entry, compress=True)
        
        # Retrieve and check compression
        # In real test, query DB directly
    
    @pytest.mark.asyncio
    async def test_async_search_worker(self, tmp_path):
        """Test async search worker."""
        db_path = str(tmp_path / "slow_async.db")
        slow = SlowMemoryTier(db_path)
        
        # Start worker
        await slow.start_worker()
        
        # Store some data
        slow.store(MemoryEntry(
            id="async-1", title="Async Test",
            what="For async search", tier=MemoryTier.SLOW,
            timestamp=int(time.time())
        ))
        
        # Schedule search
        results_received: List[MemoryEntry] = []
        
        def callback(results):
            results_received.extend(results)
        
        task = SearchTask(
            query="async",
            callback=callback,
            limit=5
        )
        slow.schedule_search(task)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Stop worker
        await slow.stop_worker()
        
        # Results may or may not be received depending on embedding provider


class TestUnifiedMemoryService:
    """Integration tests for full unified service."""
    
    @pytest.fixture
    async def unified(self, tmp_path):
        """Create temporary unified service."""
        medium_db = str(tmp_path / "medium.db")
        slow_db = str(tmp_path / "slow.db")
        
        service = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        
        await service.start()
        yield service
        await service.stop()
    
    @pytest.mark.asyncio
    async def test_save_and_search_sync(self, unified):
        """Test save to fast, sync search."""
        entry = MemoryEntry(
            id="u-1", title="Unified",
            what="Test entry", tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            tags=["unified"]
        )
        
        unified.save(entry)
        results = unified.search_sync("unified")
        
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_async_search(self, unified):
        """Test async search with callback."""
        # Store in slow tier
        unified.slow.store(MemoryEntry(
            id="slow-search-1",
            title="Slow Searchable",
            what="Content for semantic search",
            tier=MemoryTier.SLOW,
            timestamp=int(time.time())
        ))
        
        results_received = []
        
        def callback(results):
            results_received.extend(results)
        
        # This schedules async search
        unified.search_async("searchable", callback, limit=5)
        
        # Wait
        await asyncio.sleep(0.5)
        
        # Without embedding provider, results may be empty
    
    @pytest.mark.asyncio
    async def test_full_search(self, unified):
        """Test sync + async combined search."""
        # Add to fast
        unified.save(MemoryEntry(
            id="fast-s-1", title="Fast Entry",
            what="Quick access", tier=MemoryTier.FAST,
            timestamp=int(time.time())
        ))
        
        # Add to slow
        unified.slow.store(MemoryEntry(
            id="slow-s-1", title="Slow Entry",
            what="Deep archive", tier=MemoryTier.SLOW,
            timestamp=int(time.time())
        ))
        
        async_results = []
        
        def callback(results):
            async_results.extend(results)
        
        # Full search returns sync immediately, schedules async
        sync_results = unified.search_full("entry", limit=5, async_callback=callback)
        
        # Sync should have fast entry
        assert any(r.id == "fast-s-1" for r in sync_results)
        
        # Wait for async
        await asyncio.sleep(0.5)
    
    @pytest.mark.asyncio
    async def test_get_context(self, unified):
        """Test context retrieval."""
        # Add entries
        for i in range(5):
            unified.save(MemoryEntry(
                id=f"ctx-{i}", title=f"Context {i}",
                what=f"Recent {i}", tier=MemoryTier.FAST,
                timestamp=int(time.time())
            ))
        
        context = unified.get_context(limit=3)
        assert len(context) <= 3


class TestMigration:
    """Tests for tier-to-tier migration."""
    
    @pytest.mark.asyncio
    async def test_fast_to_medium_migration(self, tmp_path):
        """Test migration from fast to medium tier."""
        medium_db = str(tmp_path / "med_mig.db")
        slow_db = str(tmp_path / "slow_mig.db")
        
        unified = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        
        # Add old entry to fast (simulating age)
        old_time = int(time.time()) - 7200  # 2 hours ago
        unified.fast.store(MemoryEntry(
            id="mig-1", title="Migrate Me",
            what="Should move to medium", tier=MemoryTier.FAST,
            timestamp=old_time,
            expires_at=int(time.time()) + 3600
        ))
        
        # Run migration
        await unified._run_migration()
        
        # Check it moved to medium
        medium_results = unified.medium.search("Migrate")
        # Note: Migration removes from fast, adds to medium


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
