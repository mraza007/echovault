"""Unified 3-tier memory system for EchoVault.

Maps to user model:
- Fast tier = Core (in-memory, 24h TTL) — synchronous, immediate
- Medium tier = Short-term (SSD, 7 days, LRU eviction) — synchronous, <100ms
- Slow tier = Long-term (HDD, semantic) — asynchronous, callback-based

Migration pipeline:
  Input → Fast (24h) → structure → Medium (LRU) → compress → Slow (semantic)
"""

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

from memory.graph_relations import GraphRelationsStore, MemoryRelation, RelationType


class MemoryTier(Enum):
    FAST = "fast"      # In-memory, 24h TTL
    MEDIUM = "medium"  # SSD, 7 days, LRU eviction
    SLOW = "slow"      # HDD, async semantic search


@dataclass
class MemoryEntry:
    """Unified memory entry across all tiers."""
    id: str
    title: str
    what: str
    tier: MemoryTier
    timestamp: int  # unix timestamp
    tags: list[str] = field(default_factory=list)
    why: Optional[str] = None
    impact: Optional[str] = None
    category: Optional[str] = None
    project: Optional[str] = None
    details: Optional[str] = None
    
    # Tier-specific metadata
    access_count: int = 0
    last_access: int = 0
    expires_at: Optional[int] = None  # For Fast tier TTL
    
    def to_embed_text(self) -> str:
        """Generate text for embedding."""
        return f"{self.title} {self.what} {self.why or ''} {self.impact or ''} {' '.join(self.tags)}"


@dataclass
class SearchTask:
    """Async search task for Slow tier."""
    query: str
    callback: Callable[[list[MemoryEntry]], None]
    limit: int = 5
    project: Optional[str] = None


class FastMemoryTier:
    """In-memory tier with 24h TTL.
    
    - SQLite :memory: with WAL
    - Synchronous access
    - Automatic cleanup of expired entries
    """
    
    TTL_SECONDS = 24 * 60 * 60  # 24 hours
    
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self._init_schema()
        self._last_cleanup = time.time()
    
    def _init_schema(self):
        """Initialize in-memory schema."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                what TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                tags TEXT,  -- JSON array
                why TEXT,
                impact TEXT,
                category TEXT,
                project TEXT,
                details TEXT,
                access_count INTEGER DEFAULT 0,
                last_access INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_expires ON memories(expires_at);
            CREATE INDEX IF NOT EXISTS idx_project ON memories(project);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
            
            -- FTS for fast text search
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, what, tags,
                content='memories',
                content_rowid='rowid'
            );
        """)
        self.db.commit()
    
    def _cleanup_expired(self):
        """Remove expired entries."""
        now = int(time.time())
        if now - self._last_cleanup < 60:  # Cleanup every 60 seconds max
            return
        
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM memories WHERE expires_at < ?", (now,))
        deleted = cursor.rowcount
        self.db.commit()
        self._last_cleanup = now
        
        if deleted > 0:
            print(f"[FastTier] Cleaned up {deleted} expired entries")
    
    def store(self, entry: MemoryEntry) -> None:
        """Store entry in fast tier."""
        self._cleanup_expired()
        
        now = int(time.time())
        entry.expires_at = now + self.TTL_SECONDS
        entry.tier = MemoryTier.FAST
        
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memories 
            (id, title, what, timestamp, expires_at, tags, why, impact, 
             category, project, details, access_count, last_access)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.title, entry.what, entry.timestamp,
            entry.expires_at, json.dumps(entry.tags), entry.why,
            entry.impact, entry.category, entry.project, entry.details,
            entry.access_count, entry.last_access
        ))
        self.db.commit()
    
    def search(self, query: str, limit: int = 5, 
               project: Optional[str] = None) -> list[MemoryEntry]:
        """Synchronous search in fast tier."""
        self._cleanup_expired()
        
        cursor = self.db.cursor()
        
        # Simple LIKE search for speed (no FTS overhead for in-memory)
        sql = """
            SELECT * FROM memories 
            WHERE (title LIKE ? OR what LIKE ?)
            AND expires_at > ?
        """
        params = [f"%{query}%", f"%{query}%", int(time.time())]
        
        if project:
            sql += " AND project = ?"
            params.append(project)
        
        sql += " ORDER BY last_access DESC, timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        results = []
        for row in cursor.fetchall():
            results.append(self._row_to_entry(row))
        
        # Update access stats
        for entry in results:
            self._touch(entry.id)
        
        return results
    
    def _touch(self, memory_id: str):
        """Update last access time."""
        now = int(time.time())
        self.db.execute("""
            UPDATE memories 
            SET access_count = access_count + 1, last_access = ?
            WHERE id = ?
        """, (now, memory_id))
        self.db.commit()
    
    def _row_to_entry(self, row) -> MemoryEntry:
        """Convert DB row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            title=row["title"],
            what=row["what"],
            tier=MemoryTier.FAST,
            timestamp=row["timestamp"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            why=row["why"],
            impact=row["impact"],
            category=row["category"],
            project=row["project"],
            details=row["details"],
            access_count=row["access_count"],
            last_access=row["last_access"],
            expires_at=row["expires_at"]
        )
    
    def get_for_migration(self, limit: int = 100) -> list[MemoryEntry]:
        """Get entries ready for migration to Medium tier."""
        # Entries older than 1 hour but not yet expired
        cutoff = int(time.time()) - 3600
        
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM memories 
            WHERE timestamp < ? AND expires_at > ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (cutoff, int(time.time()), limit))
        
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def search_by_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 100,
        project: Optional[str] = None
    ) -> list[MemoryEntry]:
        """Search entries within timestamp range.
        
        Args:
            start_timestamp: Unix timestamp (inclusive)
            end_timestamp: Unix timestamp (inclusive)
            limit: Max results
            project: Optional project filter
            
        Returns:
            List of entries in time range, sorted by timestamp desc
        """
        cursor = self.db.cursor()
        
        sql = """
            SELECT * FROM memories 
            WHERE timestamp >= ? AND timestamp <= ?
            AND expires_at > ?
        """
        params = [start_timestamp, end_timestamp, int(time.time())]
        
        if project:
            sql += " AND project = ?"
            params.append(project)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        results = [self._row_to_entry(row) for row in cursor.fetchall()]
        
        # Update access stats
        for entry in results:
            self._touch(entry.id)
        
        return results
    
    def remove(self, memory_id: str) -> bool:
        """Remove entry from fast tier."""
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.db.commit()
        return cursor.rowcount > 0


class MediumMemoryTier:
    """SSD tier with LRU eviction (7 days retention, size-limited).
    
    - Persistent SQLite on SSD
    - LRU eviction when size limit reached
    - Synchronous access, <100ms
    """
    
    RETENTION_DAYS = 7
    DEFAULT_SIZE_LIMIT_MB = 500
    
    def __init__(self, db_path: str, size_limit_mb: Optional[int] = None):
        self.db_path = db_path
        self.size_limit_mb = size_limit_mb or self.DEFAULT_SIZE_LIMIT_MB
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._init_schema()
    
    def _init_schema(self):
        """Initialize medium tier schema."""
        self.db.executescript(f"""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                what TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                tags TEXT,  -- JSON array
                why TEXT,
                impact TEXT,
                category TEXT,
                project TEXT,
                details TEXT,
                access_count INTEGER DEFAULT 0,
                last_access INTEGER DEFAULT 0,
                CHECK(last_access >= timestamp)
            );
            
            CREATE INDEX IF NOT EXISTS idx_project ON memories(project);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
            CREATE INDEX IF NOT EXISTS idx_access ON memories(last_access);
            CREATE INDEX IF NOT EXISTS idx_category ON memories(category);
            
            -- FTS5 for medium tier
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, what, tags,
                content='memories',
                content_rowid='rowid'
            );
            
            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, what, tags)
                VALUES (new.rowid, new.title, new.what, new.tags);
            END;
            
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, what, tags)
                VALUES ('delete', old.rowid, old.title, old.what, old.tags);
            END;
            
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, what, tags)
                VALUES ('delete', old.rowid, old.title, old.what, old.tags);
                INSERT INTO memories_fts(rowid, title, what, tags)
                VALUES (new.rowid, new.title, new.what, new.tags);
            END;
        """)
        self.db.commit()
    
    def store(self, entry: MemoryEntry) -> None:
        """Store entry in medium tier."""
        entry.tier = MemoryTier.MEDIUM
        
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memories 
            (id, title, what, timestamp, tags, why, impact, 
             category, project, details, access_count, last_access)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.title, entry.what, entry.timestamp,
            json.dumps(entry.tags), entry.why, entry.impact,
            entry.category, entry.project, entry.details,
            entry.access_count, entry.last_access or entry.timestamp
        ))
        self.db.commit()
        
        # Check if we need to evict
        self._maybe_evict()
    
    def _maybe_evict(self):
        """LRU eviction if size limit exceeded."""
        # Check current size
        size_mb = self._get_db_size_mb()
        
        if size_mb < self.size_limit_mb:
            return
        
        # Calculate how much to evict (10% of limit)
        target_mb = self.size_limit_mb * 0.9
        
        # Evict oldest by last_access
        cutoff = int(time.time()) - (self.RETENTION_DAYS * 24 * 60 * 60)
        
        cursor = self.db.cursor()
        
        # First: remove entries older than retention period
        cursor.execute("""
            DELETE FROM memories 
            WHERE timestamp < ?
        """, (cutoff,))
        
        deleted_old = cursor.rowcount
        
        # If still over limit, evict by LRU
        if self._get_db_size_mb() > target_mb:
            # Get count to evict
            cursor.execute("SELECT COUNT(*) FROM memories")
            total = cursor.fetchone()[0]
            
            # Evict 5% of oldest by last_access
            to_evict = max(int(total * 0.05), 10)
            
            cursor.execute("""
                DELETE FROM memories 
                WHERE id IN (
                    SELECT id FROM memories 
                    ORDER BY last_access ASC, access_count ASC
                    LIMIT ?
                )
            """, (to_evict,))
            
            deleted_lru = cursor.rowcount
            print(f"[MediumTier] Evicted {deleted_old} old + {deleted_lru} LRU entries")
        
        self.db.commit()
    
    def _get_db_size_mb(self) -> float:
        """Get current database size in MB."""
        try:
            size_bytes = os.path.getsize(self.db_path)
            return size_bytes / (1024 * 1024)
        except OSError:
            return 0.0
    
    def search(self, query: str, limit: int = 5,
               project: Optional[str] = None) -> list[MemoryEntry]:
        """Synchronous search in medium tier using FTS."""
        cursor = self.db.cursor()
        
        # Use FTS5 for better search
        try:
            if project:
                cursor.execute("""
                    SELECT m.* FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE memories_fts MATCH ? AND m.project = ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, project, limit))
            else:
                cursor.execute("""
                    SELECT m.* FROM memories m
                    JOIN memories_fts fts ON m.rowid = fts.rowid
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, limit))
            
            results = [self._row_to_entry(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            # Fallback to LIKE if FTS fails
            results = self._search_like(query, limit, project)
        
        # Update access stats
        for entry in results:
            self._touch(entry.id)
        
        return results
    
    def _search_like(self, query: str, limit: int,
                     project: Optional[str]) -> list[MemoryEntry]:
        """Fallback LIKE search."""
        cursor = self.db.cursor()
        
        sql = """
            SELECT * FROM memories 
            WHERE (title LIKE ? OR what LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%"]
        
        if project:
            sql += " AND project = ?"
            params.append(project)
        
        sql += " ORDER BY last_access DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]
    
    def _touch(self, memory_id: str):
        """Update last access time."""
        now = int(time.time())
        self.db.execute("""
            UPDATE memories 
            SET access_count = access_count + 1, last_access = ?
            WHERE id = ?
        """, (now, memory_id))
        self.db.commit()
    
    def _row_to_entry(self, row) -> MemoryEntry:
        """Convert DB row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            title=row["title"],
            what=row["what"],
            tier=MemoryTier.MEDIUM,
            timestamp=row["timestamp"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            why=row["why"],
            impact=row["impact"],
            category=row["category"],
            project=row["project"],
            details=row["details"],
            access_count=row["access_count"],
            last_access=row["last_access"]
        )
    
    def search_by_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 100,
        project: Optional[str] = None
    ) -> list[MemoryEntry]:
        """Search entries within timestamp range.
        
        Args:
            start_timestamp: Unix timestamp (inclusive)
            end_timestamp: Unix timestamp (inclusive)
            limit: Max results
            project: Optional project filter
            
        Returns:
            List of entries in time range, sorted by timestamp desc
        """
        cursor = self.db.cursor()
        
        sql = """
            SELECT * FROM memories 
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_timestamp, end_timestamp]
        
        if project:
            sql += " AND project = ?"
            params.append(project)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        results = [self._row_to_entry(row) for row in cursor.fetchall()]
        
        # Update access stats
        for entry in results:
            self._touch(entry.id)
        
        return results
    
    def get_for_migration(self, limit: int = 50) -> list[MemoryEntry]:
        """Get entries ready for migration to Slow tier.
        
        Criteria: low access count, old, not accessed recently.
        """
        # Entries older than 3 days with low access
        cutoff_time = int(time.time()) - (3 * 24 * 60 * 60)
        cutoff_access = int(time.time()) - (24 * 60 * 60)  # Not accessed in 24h
        
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT * FROM memories 
            WHERE timestamp < ? 
            AND (access_count < 3 OR last_access < ?)
            ORDER BY access_count ASC, timestamp ASC
            LIMIT ?
        """, (cutoff_time, cutoff_access, limit))
        
        return [self._row_to_entry(row) for row in cursor.fetchall()]


class SlowMemoryTier:
    """HDD tier with async semantic search.
    
    - Persistent SQLite on HDD
    - Async semantic search via Ollama
    - Callback-based results (non-blocking)
    - Semantic compression for storage efficiency
    """
    
    def __init__(self, db_path: str, embedding_provider=None, compression_provider=None):
        self.db_path = db_path
        self.embedding_provider = embedding_provider
        self.compression_provider = compression_provider
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.search_queue = asyncio.Queue()
        self._init_schema()
        self._search_task: Optional[asyncio.Task] = None
    
    def _init_schema(self):
        """Initialize slow tier schema."""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                what TEXT NOT NULL,
                summary TEXT,  -- Compressed/semantic summary
                timestamp INTEGER NOT NULL,
                tags TEXT,  -- JSON array
                category TEXT,
                project TEXT,
                embedding BLOB,  -- Serialized vector
                access_count INTEGER DEFAULT 0,
                compressed_at INTEGER
            );
            
            CREATE INDEX IF NOT EXISTS idx_project ON memories(project);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);
            
            -- Virtual table for vec0 (if sqlite-vec available)
            -- Fallback: store embeddings as BLOB
        """)
        self.db.commit()
    
    async def start_worker(self):
        """Start the async search worker."""
        if self._search_task is None or self._search_task.done():
            self._search_task = asyncio.create_task(self._search_worker())
    
    async def stop_worker(self):
        """Stop the async search worker."""
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
            try:
                await self._search_task
            except asyncio.CancelledError:
                pass
    
    async def _search_worker(self):
        """Background worker for async semantic search."""
        while True:
            try:
                task: SearchTask = await self.search_queue.get()
                
                # Perform semantic search
                results = await self._semantic_search(
                    task.query, task.limit, task.project
                )
                
                # Call back with results
                try:
                    task.callback(results)
                except Exception as e:
                    print(f"[SlowTier] Callback error: {e}")
                
                self.search_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SlowTier] Worker error: {e}")
                await asyncio.sleep(1)  # Backoff on error
    
    async def _semantic_search(self, query: str, limit: int,
                                  project: Optional[str]) -> list[MemoryEntry]:
        """Perform semantic search using embeddings."""
        if not self.embedding_provider:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_provider.embed(query)
            
            # Get all entries with embeddings
            cursor = self.db.cursor()
            if project:
                cursor.execute(
                    "SELECT * FROM memories WHERE project = ? AND embedding IS NOT NULL",
                    (project,)
                )
            else:
                cursor.execute("SELECT * FROM memories WHERE embedding IS NOT NULL")
            
            # Calculate similarities
            scored = []
            for row in cursor.fetchall():
                entry = self._row_to_entry(row)
                if row["embedding"]:
                    stored = json.loads(row["embedding"])
                    similarity = self._cosine_similarity(query_embedding, stored)
                    scored.append((similarity, entry))
            
            # Sort by similarity and take top
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [entry for _, entry in scored[:limit]]
            
            # Update access stats
            for entry in results:
                self._touch(entry.id)
            
            return results
            
        except Exception as e:
            print(f"[SlowTier] Semantic search error: {e}")
            return []
    
    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def schedule_search(self, task: SearchTask) -> None:
        """Schedule an async search. Non-blocking."""
        try:
            self.search_queue.put_nowait(task)
        except asyncio.QueueFull:
            print("[SlowTier] Search queue full, dropping task")
    
    def store(self, entry: MemoryEntry, compress: bool = True) -> None:
        """Store entry in slow tier with optional compression."""
        entry.tier = MemoryTier.SLOW
        
        # Generate embedding if provider available
        embedding_blob = None
        if self.embedding_provider:
            try:
                embedding = self.embedding_provider.embed(entry.to_embed_text())
                embedding_blob = json.dumps(embedding)
            except Exception as e:
                print(f"[SlowTier] Embedding failed: {e}")
        
        # Compress if requested
        summary = None
        if compress and entry.details:
            summary = self._compress_details(entry.details)
        
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memories 
            (id, title, what, summary, timestamp, tags, category,
             project, embedding, compressed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id, entry.title, entry.what, summary,
            entry.timestamp, json.dumps(entry.tags), entry.category,
            entry.project, embedding_blob, int(time.time()) if compress else None
        ))
        self.db.commit()
    
    def _compress_details(self, details: str, max_chars: int = 500) -> str:
        """Compress details to semantic summary."""
        if self.compression_provider:
            return self.compression_provider.compress(details, max_chars)
        
        # Fallback to simple truncation
        if len(details) <= max_chars:
            return details
        
        paragraphs = [p.strip() for p in details.split("\n\n") if p.strip()]
        if len(paragraphs) <= 2:
            return details[:max_chars] + "..."
        
        first = paragraphs[0]
        last = paragraphs[-1]
        
        summary = f"{first}\n\n...\n\n{last}"
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."
        
        return summary
    
    def _touch(self, memory_id: str):
        """Update access count."""
        self.db.execute("""
            UPDATE memories SET access_count = access_count + 1
            WHERE id = ?
        """, (memory_id,))
        self.db.commit()
    
    def _row_to_entry(self, row) -> MemoryEntry:
        """Convert DB row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            title=row["title"],
            what=row["what"],
            tier=MemoryTier.SLOW,
            timestamp=row["timestamp"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            category=row["category"],
            project=row["project"],
            details=row["summary"],  # Use compressed summary
            access_count=row["access_count"]
        )
    
    def search_by_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 100,
        project: Optional[str] = None
    ) -> list[MemoryEntry]:
        """Search entries within timestamp range.
        
        Args:
            start_timestamp: Unix timestamp (inclusive)
            end_timestamp: Unix timestamp (inclusive)
            limit: Max results
            project: Optional project filter
            
        Returns:
            List of entries in time range, sorted by timestamp desc
        """
        cursor = self.db.cursor()
        
        sql = """
            SELECT * FROM memories 
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_timestamp, end_timestamp]
        
        if project:
            sql += " AND project = ?"
            params.append(project)
        
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        results = [self._row_to_entry(row) for row in cursor.fetchall()]
        
        # Update access stats
        for entry in results:
            self._touch(entry.id)
        
        return results


class UnifiedMemoryService:
    """Unified 3-tier memory service.
    
    Coordinates Fast (in-mem), Medium (SSD), Slow (HDD) tiers
    with automatic migration and async semantic search.
    """
    
    def __init__(self, 
                 fast_db: Optional[FastMemoryTier] = None,
                 medium_db_path: Optional[str] = None,
                 slow_db_path: Optional[str] = None,
                 embedding_provider=None,
                 compression_provider=None):
        """Initialize unified memory service.
        
        Args:
            fast_db: Fast tier (in-memory), created if None
            medium_db_path: Path to medium tier DB (SSD)
            slow_db_path: Path to slow tier DB (HDD)
            embedding_provider: Provider for semantic embeddings
            compression_provider: Provider for LLM-based compression
        """
        self.fast = fast_db or FastMemoryTier()
        self.medium = MediumMemoryTier(
            medium_db_path or os.path.expanduser("~/.memory/medium.db")
        )
        self.slow = SlowMemoryTier(
            slow_db_path or os.path.expanduser("~/.memory/slow.db"),
            embedding_provider,
            compression_provider
        )
        self.graph = GraphRelationsStore(slow_db_path or os.path.expanduser("~/.memory/slow.db"))
        
        self.embedding_provider = embedding_provider
        self.compression_provider = compression_provider
        self._migration_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start background tasks (search worker, migration)."""
        await self.slow.start_worker()
        self._migration_task = asyncio.create_task(self._migration_loop())
    
    async def stop(self):
        """Stop background tasks."""
        if self._migration_task:
            self._migration_task.cancel()
            try:
                await self._migration_task
            except asyncio.CancelledError:
                pass
        
        await self.slow.stop_worker()
    
    async def _migration_loop(self):
        """Background loop for tier migration."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._run_migration()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[UnifiedMemory] Migration error: {e}")
                await asyncio.sleep(60)
    
    async def _run_migration(self):
        """Run migration between tiers."""
        # Fast → Medium: entries ready for structuring
        fast_candidates = self.fast.get_for_migration(limit=20)
        for entry in fast_candidates:
            # "Structure" - just move to medium for now
            # In future: could do NLP structuring here
            self.medium.store(entry)
            self.fast.remove(entry.id)
        
        if fast_candidates:
            print(f"[UnifiedMemory] Migrated {len(fast_candidates)} Fast→Medium")
        
        # Medium → Slow: low-access, old entries
        medium_candidates = self.medium.get_for_migration(limit=10)
        for entry in medium_candidates:
            # Compress and move to slow
            self.slow.store(entry, compress=True)
            # Note: We don't delete from medium immediately
            # Could add "archived" flag instead
        
        if medium_candidates:
            print(f"[UnifiedMemory] Migrated {len(medium_candidates)} Medium→Slow")
    
    def save(self, entry: MemoryEntry) -> None:
        """Save entry to Fast tier (entry point)."""
        if not entry.id:
            entry.id = str(uuid.uuid4())
        if not entry.timestamp:
            entry.timestamp = int(time.time())
        
        self.fast.store(entry)
    
    def search_sync(self, query: str, limit: int = 5,
                    project: Optional[str] = None) -> list[MemoryEntry]:
        """Synchronous search across Fast and Medium tiers.
        
        Returns immediately with best-effort results.
        """
        # Search Fast tier
        fast_results = self.fast.search(query, limit, project)
        
        # If not enough, search Medium
        if len(fast_results) < limit:
            remaining = limit - len(fast_results)
            medium_results = self.medium.search(query, remaining, project)
            
            # Merge, avoiding duplicates
            seen_ids = {r.id for r in fast_results}
            for entry in medium_results:
                if entry.id not in seen_ids:
                    fast_results.append(entry)
        
        return fast_results[:limit]
    
    def search_async(self, query: str, callback: Callable,
                     limit: int = 5, project: Optional[str] = None) -> None:
        """Asynchronous semantic search in Slow tier.
        
        Non-blocking. Results delivered via callback.
        """
        task = SearchTask(
            query=query,
            callback=callback,
            limit=limit,
            project=project
        )
        self.slow.schedule_search(task)
    
    def search_full(self, query: str, limit: int = 5,
                    project: Optional[str] = None,
                    async_callback: Optional[Callable] = None) -> list[MemoryEntry]:
        """Full search: sync (Fast+Medium) + async (Slow).
        
        Returns sync results immediately, schedules async search.
        """
        # Get sync results immediately
        sync_results = self.search_sync(query, limit, project)
        
        # Schedule async search if callback provided
        if async_callback:
            self.search_async(query, async_callback, limit, project)
        
        return sync_results
    
    def search_by_time_range(
        self,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 100,
        project: Optional[str] = None
    ) -> list[MemoryEntry]:
        """Search entries within timestamp range (sync + async aggregation).
        
        Searches Fast and Medium tiers synchronously,
        schedules async search in Slow tier.
        
        Args:
            start_timestamp: Unix timestamp (inclusive)
            end_timestamp: Unix timestamp (inclusive)
            limit: Max results per tier
            project: Optional project filter
            
        Returns:
            List of entries in time range, sorted by timestamp desc
        """
        # Search Fast tier
        fast_results = self.fast.search_by_time_range(
            start_timestamp, end_timestamp, limit, project
        )
        
        # Search Medium tier
        medium_results = self.medium.search_by_time_range(
            start_timestamp, end_timestamp, limit, project
        )
        
        # Merge results, avoiding duplicates
        seen_ids = {r.id for r in fast_results}
        all_results = list(fast_results)
        
        for entry in medium_results:
            if entry.id not in seen_ids:
                all_results.append(entry)
                seen_ids.add(entry.id)
        
        # Sort by timestamp desc
        all_results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return all_results[:limit]
    
    def search_by_date(
        self,
        year: int,
        month: Optional[int] = None,
        day: Optional[int] = None,
        limit: int = 100,
        project: Optional[str] = None
    ) -> list[MemoryEntry]:
        """Search by calendar date (convenience method).
        
        Examples:
            search_by_date(2025, 3)  # March 2025
            search_by_date(2025, 3, 15)  # March 15, 2025
        
        Args:
            year: Year (e.g., 2025)
            month: Optional month (1-12)
            day: Optional day (1-31)
            limit: Max results
            project: Optional project filter
            
        Returns:
            List of entries in date range
        """
        import calendar
        
        # Calculate timestamp range
        if month and day:
            # Specific day
            from datetime import datetime
            start = datetime(year, month, day, 0, 0, 0)
            end = datetime(year, month, day, 23, 59, 59)
        elif month:
            # Whole month
            from datetime import datetime
            start = datetime(year, month, 1, 0, 0, 0)
            last_day = calendar.monthrange(year, month)[1]
            end = datetime(year, month, last_day, 23, 59, 59)
        else:
            # Whole year
            from datetime import datetime
            start = datetime(year, 1, 1, 0, 0, 0)
            end = datetime(year, 12, 31, 23, 59, 59)
        
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        
        return self.search_by_time_range(start_ts, end_ts, limit, project)

    def get_context(self, limit: int = 10,
                    project: Optional[str] = None) -> list[MemoryEntry]:
        """Get recent context from Fast and Medium tiers."""
        # Get recent from Fast
        fast_recent = self.fast.search("", limit=limit, project=project)
        
        # Fill from Medium if needed
        if len(fast_recent) < limit:
            remaining = limit - len(fast_recent)
            # Use empty query to get recent by timestamp
            medium_recent = self.medium.search("", limit=remaining, project=project)
            
            seen = {r.id for r in fast_recent}
            for entry in medium_recent:
                if entry.id not in seen:
                    fast_recent.append(entry)
        
        return fast_recent[:limit]


# Factory function for easy creation
def create_unified_memory(
    memory_home: Optional[str] = None,
    embedding_provider=None,
    compression_provider=None,
    cache_embeddings: bool = True,
    cache_maxsize: int = 1000,
) -> UnifiedMemoryService:
    """Create a unified memory service with standard paths.
    
    Args:
        memory_home: Base directory for memory files
        embedding_provider: Provider for semantic embeddings (auto-cached if enabled)
        compression_provider: Provider for LLM-based compression (e.g., OllamaCompressor)
        cache_embeddings: Whether to wrap provider in LRU cache
        cache_maxsize: Max cache entries for embeddings
    """
    home = memory_home or os.path.expanduser("~/.memory")
    
    os.makedirs(home, exist_ok=True)
    
    # Wrap provider in cache if requested
    if embedding_provider and cache_embeddings:
        from memory.embeddings.cache import CachedEmbeddingProvider
        embedding_provider = CachedEmbeddingProvider(
            embedding_provider, 
            maxsize=cache_maxsize
        )
    
    return UnifiedMemoryService(
        medium_db_path=os.path.join(home, "medium.db"),
        slow_db_path=os.path.join(home, "slow.db"),
        embedding_provider=embedding_provider,
        compression_provider=compression_provider
    )
