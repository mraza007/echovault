"""Tests for temporal (time-based) queries in unified memory."""

import time
import pytest
from datetime import datetime
from memory.unified import (
    FastMemoryTier,
    MediumMemoryTier,
    SlowMemoryTier,
    UnifiedMemoryService,
    MemoryEntry,
    MemoryTier,
)


class TestTemporalQueriesFastTier:
    """Temporal search tests for FastMemoryTier."""
    
    def test_search_by_time_range_basic(self):
        fast = FastMemoryTier()
        
        # Create entries at different times
        now = int(time.time())
        
        entry1 = MemoryEntry(
            id="1", title="Today", what="Recent entry",
            tier=MemoryTier.FAST, timestamp=now
        )
        entry2 = MemoryEntry(
            id="2", title="Yesterday", what="Older entry",
            tier=MemoryTier.FAST, timestamp=now - 86400
        )
        
        fast.store(entry1)
        fast.store(entry2)
        
        # Search for today only
        results = fast.search_by_time_range(now - 3600, now + 3600)
        assert len(results) == 1
        assert results[0].id == "1"
    
    def test_search_by_time_range_with_project(self):
        fast = FastMemoryTier()
        now = int(time.time())
        
        entry1 = MemoryEntry(
            id="1", title="Proj A", what="Entry A",
            tier=MemoryTier.FAST, timestamp=now, project="ProjectA"
        )
        entry2 = MemoryEntry(
            id="2", title="Proj B", what="Entry B",
            tier=MemoryTier.FAST, timestamp=now, project="ProjectB"
        )
        
        fast.store(entry1)
        fast.store(entry2)
        
        results = fast.search_by_time_range(now - 3600, now + 3600, project="ProjectA")
        assert len(results) == 1
        assert results[0].project == "ProjectA"


class TestTemporalQueriesMediumTier:
    """Temporal search tests for MediumMemoryTier."""
    
    def test_search_by_time_range_sort_order(self):
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            medium = MediumMemoryTier(db_path)
            
            # Create entries with different timestamps
            base_time = 1609459200  # 2021-01-01 00:00:00 UTC
            
            for i in range(5):
                entry = MemoryEntry(
                    id=str(i),
                    title=f"Entry {i}",
                    what=f"Content {i}",
                    tier=MemoryTier.MEDIUM,
                    timestamp=base_time + (i * 86400)  # Daily
                )
                medium.store(entry)
            
            # Search all, should be sorted desc
            results = medium.search_by_time_range(base_time, base_time + 5 * 86400, limit=10)
            assert len(results) == 5
            
            # Check descending order
            for i in range(len(results) - 1):
                assert results[i].timestamp >= results[i + 1].timestamp
        finally:
            os.unlink(db_path)


class TestTemporalQueriesUnified:
    """Temporal search tests for UnifiedMemoryService."""
    
    def test_search_by_time_range_across_tiers(self):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                medium_db_path=os.path.join(tmpdir, "medium.db"),
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            now = int(time.time())
            yesterday = now - 86400
            
            # Entry in Fast tier
            fast_entry = MemoryEntry(
                id="fast-1", title="Fast Entry", what="In fast tier",
                tier=MemoryTier.FAST, timestamp=now
            )
            memory.save(fast_entry)
            
            # Entry in Medium tier (simulate migration by storing directly)
            medium_entry = MemoryEntry(
                id="medium-1", title="Medium Entry", what="In medium tier",
                tier=MemoryTier.MEDIUM, timestamp=yesterday
            )
            memory.medium.store(medium_entry)
            
            # Search across tiers
            results = memory.search_by_time_range(yesterday - 3600, now + 3600)
            
            # Should find both
            ids = {r.id for r in results}
            assert "fast-1" in ids
            assert "medium-1" in ids
    
    def test_search_by_date_year_only(self):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                medium_db_path=os.path.join(tmpdir, "medium.db"),
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            # Entry from 2025
            entry_2025 = MemoryEntry(
                id="2025-entry",
                title="2025 Entry",
                what="From 2025",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2025, 6, 15).timestamp())
            )
            memory.medium.store(entry_2025)
            
            # Entry from 2024
            entry_2024 = MemoryEntry(
                id="2024-entry",
                title="2024 Entry",
                what="From 2024",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2024, 6, 15).timestamp())
            )
            memory.medium.store(entry_2024)
            
            # Search 2025
            results = memory.search_by_date(2025)
            assert len(results) == 1
            assert results[0].id == "2025-entry"
    
    def test_search_by_date_month(self):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                medium_db_path=os.path.join(tmpdir, "medium.db"),
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            # Entries in March and April 2025
            march_entry = MemoryEntry(
                id="march",
                title="March Entry",
                what="From March",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2025, 3, 15).timestamp())
            )
            april_entry = MemoryEntry(
                id="april",
                title="April Entry",
                what="From April",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2025, 4, 15).timestamp())
            )
            memory.medium.store(march_entry)
            memory.medium.store(april_entry)
            
            # Search March 2025
            results = memory.search_by_date(2025, month=3)
            assert len(results) == 1
            assert results[0].id == "march"
    
    def test_search_by_date_specific_day(self):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                medium_db_path=os.path.join(tmpdir, "medium.db"),
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            # Entries on different days
            day1_entry = MemoryEntry(
                id="day1",
                title="Day 1 Entry",
                what="From March 1",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2025, 3, 1, 12, 0, 0).timestamp())
            )
            day2_entry = MemoryEntry(
                id="day2",
                title="Day 2 Entry",
                what="From March 2",
                tier=MemoryTier.MEDIUM,
                timestamp=int(datetime(2025, 3, 2, 12, 0, 0).timestamp())
            )
            memory.medium.store(day1_entry)
            memory.medium.store(day2_entry)
            
            # Search March 1, 2025
            results = memory.search_by_date(2025, month=3, day=1)
            assert len(results) == 1
            assert results[0].id == "day1"


class TestTemporalQueriesEdgeCases:
    """Edge cases for temporal queries."""
    
    def test_empty_time_range(self):
        fast = FastMemoryTier()
        
        # Search empty range
        now = int(time.time())
        results = fast.search_by_time_range(now + 1000, now + 2000)
        assert len(results) == 0
    
    def test_no_duplicate_results(self):
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = UnifiedMemoryService(
                medium_db_path=os.path.join(tmpdir, "medium.db"),
                slow_db_path=os.path.join(tmpdir, "slow.db"),
            )
            
            now = int(time.time())
            
            # Same entry ID in both tiers (shouldn't happen in practice, but test dedup)
            entry = MemoryEntry(
                id="same-id",
                title="Test",
                what="Test entry",
                tier=MemoryTier.FAST,
                timestamp=now
            )
            
            memory.save(entry)
            memory.medium.store(entry)  # Also in medium
            
            results = memory.search_by_time_range(now - 3600, now + 3600)
            
            # Should deduplicate
            ids = [r.id for r in results]
            assert ids.count("same-id") == 1
