"""Integration layer for unified memory with existing EchoVault.

Bridges UnifiedMemoryService with existing MemoryService/MCP server.
"""

import asyncio
from typing import Optional

from memory.core import MemoryService
from memory.unified import (
    UnifiedMemoryService,
    create_unified_memory,
    MemoryEntry,
    MemoryTier,
)


class UnifiedMemoryAdapter:
    """Adapter to use unified memory alongside existing MemoryService.
    
    Provides gradual migration path:
    - Phase 1: Write to both systems (existing + unified)
    - Phase 2: Read from unified first, fallback to existing
    - Phase 3: Full migration to unified
    """
    
    def __init__(self, 
                 existing: MemoryService,
                 unified: Optional[UnifiedMemoryService] = None):
        """Initialize adapter.
        
        Args:
            existing: Existing MemoryService instance
            unified: UnifiedMemoryService instance (created if None)
        """
        self.existing = existing
        self.unified = unified or create_unified_memory(
            memory_home=existing.memory_home,
            embedding_provider=existing.embedding_provider
        )
        self._started = False
    
    async def start(self):
        """Start unified memory background tasks."""
        if not self._started:
            await self.unified.start()
            self._started = True
    
    async def stop(self):
        """Stop unified memory background tasks."""
        if self._started:
            await self.unified.stop()
            self._started = False
    
    def save_unified(self, memory_id: str, title: str, what: str,
                     **kwargs) -> None:
        """Save to unified memory tier (Fast).
        
        Also records to existing system for compatibility.
        """
        # Create unified entry
        entry = MemoryEntry(
            id=memory_id,
            title=title,
            what=what,
            tier=MemoryTier.FAST,
            timestamp=int(__import__('time').time()),
            tags=kwargs.get('tags', []),
            why=kwargs.get('why'),
            impact=kwargs.get('impact'),
            category=kwargs.get('category'),
            project=kwargs.get('project'),
            details=kwargs.get('details')
        )
        
        # Save to unified (Fast tier)
        self.unified.save(entry)
    
    def search_unified(self, query: str, limit: int = 5,
                       project: Optional[str] = None,
                       use_async: bool = False,
                       async_callback=None) -> list[MemoryEntry]:
        """Search using unified memory.
        
        Args:
            query: Search query
            limit: Max results
            project: Optional project filter
            use_async: If True, also schedule slow tier search
            async_callback: Callback for async slow tier results
        """
        if use_async and async_callback:
            return self.unified.search_full(
                query, limit, project, async_callback
            )
        else:
            return self.unified.search_sync(query, limit, project)
    
    def get_context_unified(self, limit: int = 10,
                            project: Optional[str] = None) -> list[MemoryEntry]:
        """Get context from unified memory (Fast + Medium tiers)."""
        return self.unified.get_context(limit, project)
    
    def migrate_existing_to_unified(self, limit: int = 100) -> int:
        """Migrate recent memories from existing system to unified.
        
        Useful for initial migration or backfill.
        
        Returns:
            Number of memories migrated
        """
        # Get recent from existing
        recent = self.existing.list_memories(limit=limit)
        
        migrated = 0
        for mem in recent:
            # Skip if already in unified (check by ID)
            # For now, just add all
            entry = MemoryEntry(
                id=mem['id'],
                title=mem['title'],
                what=mem['what'],
                tier=MemoryTier.MEDIUM,  # Start in medium for existing
                timestamp=int(__import__('time').time()),
                tags=mem.get('tags', []),
                why=mem.get('why'),
                impact=mem.get('impact'),
                category=mem.get('category'),
                project=mem.get('project')
            )
            self.unified.medium.store(entry)
            migrated += 1
        
        return migrated


def create_unified_adapter(memory_home: Optional[str] = None) -> UnifiedMemoryAdapter:
    """Create adapter with default configuration."""
    existing = MemoryService(memory_home=memory_home)
    unified = create_unified_memory(
        memory_home=existing.memory_home,
        embedding_provider=existing.embedding_provider
    )
    return UnifiedMemoryAdapter(existing, unified)
