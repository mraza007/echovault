"""MCP server tools for unified 3-tier memory system.

Exposes unified memory to Windsurf/Kiro IDE.
"""

import json
from typing import Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

from memory.unified import (
    UnifiedMemoryService,
    MemoryEntry,
    MemoryTier,
    create_unified_memory,
)
from memory.rollback import (
    RollbackManager,
    FeatureState,
    get_manager,
)


# Global service instance
_unified_service: Optional[UnifiedMemoryService] = None

def get_unified_service() -> UnifiedMemoryService:
    """Get or create unified memory service."""
    global _unified_service
    if _unified_service is None:
        _unified_service = create_unified_memory()
    return _unified_service


UNIFIED_SEARCH_DESCRIPTION = """Search unified memory system (Fast + Medium tiers).

Returns results immediately from Fast (in-memory) and Medium (SSD) tiers.
For deep archive search, use memory_search_unified_async."""

UNIFIED_ASYNC_SEARCH_DESCRIPTION = """Async search in Slow tier (semantic, archive).

Non-blocking search that returns results via callback.
Uses semantic embeddings for matching. Results arrive later."""

UNIFIED_SAVE_DESCRIPTION = """Save to unified memory (Fast tier).

Entry starts in Fast tier (24h TTL), migrates to Medium (7d), then Slow (archive).
Use this for all new memories - the system handles tier management."""

UNIFIED_CONTEXT_DESCRIPTION = """Get context from Fast and Medium tiers.

Retrieves recent memories for context injection.
Faster than search - no query processing needed."""

ROLLBACK_STATUS_DESCRIPTION = """Check rollback system status.

Shows current feature flags, error rates, and backup status.
Use to verify system health before enabling unified memory."""

ROLLBACK_ENABLE_DESCRIPTION = """Enable unified memory system.

Stages:
- shadow: Write to both systems (safe testing)
- canary: 10% traffic to new system (gradual rollout)
- enabled: Full unified system

Use with caution - always backup first!"""

ROLLBACK_EMERGENCY_DESCRIPTION = """Emergency rollback to legacy system.

Instantly disables unified memory and restores legacy mode.
Use if unified system shows errors or performance issues."""


def create_unified_tools(server: Server, rollback_manager: Optional[RollbackManager] = None):
    """Add unified memory tools to MCP server."""
    
    manager = rollback_manager or get_manager()
    
    @server.list_tools()
    async def list_tools():
        tools = []
        
        # Only add unified tools if enabled
        if manager.should_use_unified():
            tools.extend([
                Tool(
                    name="memory_unified_search",
                    description=UNIFIED_SEARCH_DESCRIPTION,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "default": 5, "description": "Max results"},
                            "project": {"type": "string", "description": "Filter by project"},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="memory_unified_context",
                    description=UNIFIED_CONTEXT_DESCRIPTION,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 10, "description": "Max memories"},
                            "project": {"type": "string", "description": "Filter by project"},
                        },
                    },
                ),
                Tool(
                    name="memory_unified_save",
                    description=UNIFIED_SAVE_DESCRIPTION,
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Memory title"},
                            "what": {"type": "string", "description": "Core content (1-2 sentences)"},
                            "why": {"type": "string", "description": "Reasoning"},
                            "impact": {"type": "string", "description": "What changed"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "category": {"type": "string", "enum": ["decision", "bug", "pattern", "learning", "context"]},
                            "project": {"type": "string", "description": "Project name"},
                            "details": {"type": "string", "description": "Full context"},
                        },
                        "required": ["title", "what"],
                    },
                ),
            ])
        
        # Rollback management tools (always available)
        tools.extend([
            Tool(
                name="memory_rollback_status",
                description=ROLLBACK_STATUS_DESCRIPTION,
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="memory_rollback_enable",
                description=ROLLBACK_ENABLE_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "stage": {
                            "type": "string",
                            "enum": ["shadow", "canary", "enabled"],
                            "description": "Rollout stage"
                        },
                    },
                    "required": ["stage"],
                },
            ),
            Tool(
                name="memory_rollback_emergency",
                description=ROLLBACK_EMERGENCY_DESCRIPTION,
                inputSchema={"type": "object", "properties": {}},
            ),
        ])
        
        return tools
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name == "memory_unified_search":
                return await handle_unified_search(**arguments)
            elif name == "memory_unified_context":
                return await handle_unified_context(**arguments)
            elif name == "memory_unified_save":
                return await handle_unified_save(**arguments)
            elif name == "memory_rollback_status":
                return await handle_rollback_status()
            elif name == "memory_rollback_enable":
                return await handle_rollback_enable(**arguments)
            elif name == "memory_rollback_emergency":
                return await handle_rollback_emergency()
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        except Exception as e:
            # Record error for rollback monitoring
            manager.record_error(e)
            return [TextContent(type="text", text=json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }))]


async def handle_unified_search(
    query: str,
    limit: int = 5,
    project: Optional[str] = None
) -> list[TextContent]:
    """Handle unified memory search."""
    service = get_unified_service()
    
    results = service.search_sync(query, limit=limit, project=project)
    
    # Format results
    formatted = []
    for entry in results:
        formatted.append({
            "id": entry.id,
            "title": entry.title,
            "what": entry.what,
            "tier": entry.tier.value,
            "timestamp": entry.timestamp,
            "tags": entry.tags,
            "project": entry.project,
        })
    
    return [TextContent(type="text", text=json.dumps({
        "results": formatted,
        "count": len(formatted),
        "query": query,
        "tier": "fast+medium"
    }, indent=2))]


async def handle_unified_context(
    limit: int = 10,
    project: Optional[str] = None
) -> list[TextContent]:
    """Handle unified memory context retrieval."""
    service = get_unified_service()
    
    context = service.get_context(limit=limit, project=project)
    
    formatted = []
    for entry in context:
        formatted.append({
            "id": entry.id,
            "title": entry.title,
            "category": entry.category,
            "tags": entry.tags,
            "tier": entry.tier.value,
        })
    
    return [TextContent(type="text", text=json.dumps({
        "context": formatted,
        "count": len(formatted),
    }, indent=2))]


async def handle_unified_save(
    title: str,
    what: str,
    why: Optional[str] = None,
    impact: Optional[str] = None,
    tags: Optional[list] = None,
    category: Optional[str] = None,
    project: Optional[str] = None,
    details: Optional[str] = None,
) -> list[TextContent]:
    """Handle unified memory save."""
    service = get_unified_service()
    
    import time
    entry = MemoryEntry(
        id=str(__import__('uuid').uuid4()),
        title=title,
        what=what,
        tier=MemoryTier.FAST,
        timestamp=int(time.time()),
        tags=tags or [],
        why=why,
        impact=impact,
        category=category,
        project=project,
        details=details,
    )
    
    service.save(entry)
    
    return [TextContent(type="text", text=json.dumps({
        "status": "saved",
        "id": entry.id,
        "tier": "fast",
        "title": title,
    }, indent=2))]


async def handle_rollback_status() -> list[TextContent]:
    """Handle rollback status check."""
    manager = get_manager()
    status = manager.get_status()
    
    return [TextContent(type="text", text=json.dumps(status, indent=2))]


async def handle_rollback_enable(stage: str) -> list[TextContent]:
    """Handle rollback enable command."""
    from memory.rollback import enable_shadow_mode, enable_canary, enable_unified
    
    if stage == "shadow":
        enable_shadow_mode()
    elif stage == "canary":
        enable_canary()
    elif stage == "enabled":
        enable_unified()
    
    return [TextContent(type="text", text=json.dumps({
        "status": "enabled",
        "stage": stage,
        "message": f"Unified memory system now in {stage} mode"
    }, indent=2))]


async def handle_rollback_emergency() -> list[TextContent]:
    """Handle emergency rollback."""
    from memory.rollback import rollback
    
    rollback()
    
    return [TextContent(type="text", text=json.dumps({
        "status": "emergency_rollback",
        "message": "Unified memory system disabled. Using legacy mode.",
        "action_required": "Investigate errors and restore from backup if needed"
    }, indent=2))]


def patch_mcp_server(existing_server: Server, rollback_manager: Optional[RollbackManager] = None):
    """Patch existing MCP server with unified memory tools."""
    create_unified_tools(existing_server, rollback_manager)
    return existing_server
