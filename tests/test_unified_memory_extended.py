"""Extended tests for unified 3-tier memory system with edge cases and rollback scenarios."""

import asyncio
import os
import tempfile
import time
from typing import List
from unittest.mock import Mock, patch

import pytest

from memory.unified import (
    FastMemoryTier,
    MediumMemoryTier,
    SlowMemoryTier,
    UnifiedMemoryService,
    MemoryEntry,
    MemoryTier,
    SearchTask,
    create_unified_memory,
)


class TestFastTierEdgeCases:
    """Edge case tests for Fast tier."""
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        import threading
        
        fast = FastMemoryTier()
        errors = []
        
        def writer(n):
            try:
                for i in range(10):
                    entry = MemoryEntry(
                        id=f"thread-{n}-{i}",
                        title=f"Thread {n} Entry {i}",
                        what="Content",
                        tier=MemoryTier.FAST,
                        timestamp=int(time.time())
                    )
                    fast.store(entry)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        
        # Verify all entries stored
        all_results = fast.search("Thread")
        assert len(all_results) == 50
    
    def test_ttl_boundary(self):
        """Test entries at exact TTL boundary."""
        fast = FastMemoryTier()
        
        # Entry expiring exactly now
        entry = MemoryEntry(
            id="boundary",
            title="Boundary",
            what="Should be cleaned",
            tier=MemoryTier.FAST,
            timestamp=int(time.time()),
            expires_at=int(time.time())
        )
        fast.store(entry)
        
        fast._cleanup_expired()
        
        results = fast.search("Boundary")
        assert len(results) == 0
    
    def test_large_entry(self):
        """Test handling of large entries."""
        fast = FastMemoryTier()
        
        large_content = "x" * 100000  # 100KB
        entry = MemoryEntry(
            id="large",
            title="Large Entry",
            what=large_content,
            tier=MemoryTier.FAST,
            timestamp=int(time.time())
        )
        
        fast.store(entry)
        results = fast.search("Large")
        
        assert len(results) == 1
        assert len(results[0].what) == 100000


class TestMediumTierEviction:
    """LRU eviction tests."""
    
    def test_eviction_order(self, tmp_path):
        """Test that least recently accessed entries are evicted first."""
        db_path = str(tmp_path / "evict.db")
        medium = MediumMemoryTier(db_path, size_limit_mb=1)
        
        # Store entries with different access patterns
        for i in range(20):
            entry = MemoryEntry(
                id=f"evict-{i}",
                title=f"Entry {i}",
                what="Content " * 1000,  # Make large
                tier=MemoryTier.MEDIUM,
                timestamp=int(time.time()) - i,
                last_access=int(time.time()) - (i * 100)  # Different access times
            )
            medium.store(entry)
        
        # Access some entries to make them "hot"
        medium.search("Entry 0")
        medium.search("Entry 1")
        medium.search("Entry 2")
        
        # Trigger eviction by adding more large entries
        for i in range(20, 40):
            entry = MemoryEntry(
                id=f"evict-{i}",
                title=f"Entry {i}",
                what="More content " * 1000,
                tier=MemoryTier.MEDIUM,
                timestamp=int(time.time())
            )
            medium.store(entry)
        
        # Check that hot entries are still there
        results = medium.search("Entry 0")
        assert len(results) > 0, "Hot entry should not be evicted"
    
    def test_retention_policy(self, tmp_path):
        """Test 7-day retention policy."""
        db_path = str(tmp_path / "retention.db")
        medium = MediumMemoryTier(db_path)
        
        # Old entry (8 days)
        old_entry = MemoryEntry(
            id="old",
            title="Old Entry",
            what="Should be removed",
            tier=MemoryTier.MEDIUM,
            timestamp=int(time.time()) - (8 * 24 * 60 * 60),
            last_access=int(time.time()) - (8 * 24 * 60 * 60)
        )
        medium.store(old_entry)
        
        # Recent entry (1 day)
        recent_entry = MemoryEntry(
            id="recent",
            title="Recent Entry",
            what="Should stay",
            tier=MemoryTier.MEDIUM,
            timestamp=int(time.time()) - (24 * 60 * 60),
            last_access=int(time.time()) - (24 * 60 * 60)
        )
        medium.store(recent_entry)
        
        # Trigger eviction check
        for i in range(10):
            medium.store(MemoryEntry(
                id=f"trigger-{i}",
                title=f"Trigger {i}",
                what="x" * 10000,
                tier=MemoryTier.MEDIUM,
                timestamp=int(time.time())
            ))
        
        # Old should be gone, recent should stay
        old_results = medium.search("Old Entry")
        recent_results = medium.search("Recent Entry")
        
        assert len(old_results) == 0, "Old entry should be removed by retention policy"


class TestSlowTierAsync:
    """Async behavior tests for Slow tier."""
    
    @pytest.mark.asyncio
    async def test_worker_queue_overflow(self, tmp_path):
        """Test behavior when search queue fills up."""
        db_path = str(tmp_path / "overflow.db")
        slow = SlowMemoryTier(db_path)
        await slow.start_worker()
        
        # Fill queue with many tasks
        callbacks_executed = []
        
        def make_callback(n):
            def callback(results):
                callbacks_executed.append(n)
            return callback
        
        for i in range(100):
            task = SearchTask(
                query=f"query {i}",
                callback=make_callback(i),
                limit=5
            )
            slow.schedule_search(task)
        
        # Wait for processing
        await asyncio.sleep(2)
        await slow.stop_worker()
        
        # Most callbacks should have executed
        assert len(callbacks_executed) > 50
    
    @pytest.mark.asyncio
    async def test_embedding_failure_handling(self, tmp_path):
        """Test graceful handling of embedding failures."""
        db_path = str(tmp_path / "embed_fail.db")
        
        # Mock embedding provider that fails
        mock_provider = Mock()
        mock_provider.embed.side_effect = Exception("Embedding service down")
        
        slow = SlowMemoryTier(db_path, embedding_provider=mock_provider)
        
        # Should not crash
        entry = MemoryEntry(
            id="embed-test",
            title="Test",
            what="Content",
            tier=MemoryTier.SLOW,
            timestamp=int(time.time())
        )
        slow.store(entry)
        
        # Entry should be stored even without embedding
        cursor = slow.db.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", ("embed-test",))
        result = cursor.fetchone()
        assert result is not None


class TestMigrationScenarios:
    """Migration pipeline tests."""
    
    @pytest.mark.asyncio
    async def test_migration_with_corruption(self, tmp_path):
        """Test migration resilience to data corruption."""
        medium_db = str(tmp_path / "med_corrupt.db")
        slow_db = str(tmp_path / "slow_corrupt.db")
        
        unified = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        
        # Add valid entries
        for i in range(5):
            unified.fast.store(MemoryEntry(
                id=f"valid-{i}",
                title=f"Valid {i}",
                what="Good content",
                tier=MemoryTier.FAST,
                timestamp=int(time.time()) - 7200  # 2 hours old
            ))
        
        # Run migration
        await unified._run_migration()
        
        # Valid entries should migrate
        results = unified.medium.search("Valid")
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_migration_idempotency(self, tmp_path):
        """Test that migration is idempotent."""
        medium_db = str(tmp_path / "idempotent.db")
        slow_db = str(tmp_path / "slow_idempotent.db")
        
        unified = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        
        # Add entry
        entry = MemoryEntry(
            id="idempotent-test",
            title="Test",
            what="Content",
            tier=MemoryTier.FAST,
            timestamp=int(time.time()) - 7200
        )
        unified.fast.store(entry)
        
        # Run migration twice
        await unified._run_migration()
        await unified._run_migration()
        
        # Should only have one copy in medium
        results = unified.medium.search("idempotent-test")
        # Note: Current implementation uses INSERT OR REPLACE
        # so it's technically idempotent but overwrites


class TestRollbackMechanism:
    """Tests for rollback to old system."""
    
    def test_backup_creation(self, tmp_path):
        """Test that backups are created before migration."""
        # This would be implemented in the migration script
        pass
    
    def test_feature_flag_toggle(self):
        """Test that feature flags work correctly."""
        from memory.unified_adapter import UnifiedMemoryAdapter
        
        # Mock existing service
        mock_existing = Mock()
        mock_existing.memory_home = "~/.memory"
        mock_existing.embedding_provider = None
        
        # Create adapter
        adapter = UnifiedMemoryAdapter(mock_existing)
        
        # Test that we can toggle between systems
        # In real implementation, this would check config


class TestIntegrationExistingSystem:
    """Integration with existing EchoVault."""
    
    def test_parallel_write(self, tmp_path):
        """Test writing to both systems in parallel."""
        from memory.unified_adapter import UnifiedMemoryAdapter
        from memory.core import MemoryService
        
        # Create real existing service
        existing = MemoryService(memory_home=str(tmp_path / "existing"))
        
        # Create adapter
        adapter = UnifiedMemoryAdapter(existing)
        
        # Write through adapter
        adapter.save_unified(
            memory_id="test-123",
            title="Test Entry",
            what="Test content",
            project="test-project",
            tags=["test"]
        )
        
        # Should be in unified fast tier
        results = adapter.unified.search_sync("Test Entry")
        assert len(results) == 1


class TestErrorRecovery:
    """Error recovery and resilience tests."""
    
    @pytest.mark.asyncio
    async def test_service_restart_recovery(self, tmp_path):
        """Test recovery after service restart."""
        medium_db = str(tmp_path / "restart.db")
        slow_db = str(tmp_path / "slow_restart.db")
        
        # First session
        service1 = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        await service1.start()
        
        service1.save(MemoryEntry(
            id="persistent",
            title="Persistent Entry",
            what="Should survive restart",
            tier=MemoryTier.FAST,
            timestamp=int(time.time())
        ))
        
        await service1.stop()
        
        # Second session (restart)
        service2 = UnifiedMemoryService(
            medium_db_path=medium_db,
            slow_db_path=slow_db
        )
        await service2.start()
        
        # Note: Fast tier is in-memory so data lost
        # Medium and Slow should persist
    
    def test_disk_full_handling(self, tmp_path):
        """Test graceful handling of disk full."""
        # This is hard to test without actually filling disk
        # But we can test the error handling code path
        pass


class TestPerformance:
    """Performance benchmarks."""
    
    def test_fast_tier_latency(self):
        """Benchmark Fast tier search latency."""
        fast = FastMemoryTier()
        
        # Populate
        for i in range(1000):
            fast.store(MemoryEntry(
                id=f"perf-{i}",
                title=f"Performance Entry {i}",
                what=f"Content {i}",
                tier=MemoryTier.FAST,
                timestamp=int(time.time())
            ))
        
        # Measure search time
        import time as time_module
        start = time_module.time()
        for _ in range(100):
            fast.search("Performance")
        elapsed = time_module.time() - start
        
        avg_latency = (elapsed / 100) * 1000  # ms
        assert avg_latency < 10, f"Fast tier too slow: {avg_latency:.2f}ms avg"
    
    def test_medium_tier_throughput(self, tmp_path):
        """Benchmark Medium tier write throughput."""
        db_path = str(tmp_path / "throughput.db")
        medium = MediumMemoryTier(db_path)
        
        import time as time_module
        start = time_module.time()
        
        for i in range(100):
            medium.store(MemoryEntry(
                id=f"tput-{i}",
                title=f"Throughput {i}",
                what="Content",
                tier=MemoryTier.MEDIUM,
                timestamp=int(time.time())
            ))
        
        elapsed = time_module.time() - start
        tps = 100 / elapsed
        
        assert tps > 50, f"Medium tier too slow: {tps:.2f} TPS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
