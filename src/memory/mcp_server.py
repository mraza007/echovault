"""MCP server exposing memory tools for coding agents."""

import json
import os
from datetime import datetime
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from memory.core import MemoryService
from memory.models import RawMemoryInput

VALID_CATEGORIES = ("decision", "bug", "pattern", "learning", "context")

SAVE_DESCRIPTION = """Save a memory for future sessions. Call this when you:
- Make an architectural or design decision (chose X over Y)
- Fix a bug (include root cause and solution)
- Discover a non-obvious pattern or gotcha
- Learn something about the codebase not obvious from code

Do NOT save: trivial changes (typos, formatting), info obvious from reading the code, or duplicates of existing memories. Write for a future agent with zero context."""

SEARCH_DESCRIPTION = """Search memories using keyword and semantic search. Returns matching memories ranked by relevance. Use this to find prior decisions, bugs, patterns, and context before starting work."""

CONTEXT_DESCRIPTION = """Get memory context for the current project. Call this at session start to load prior decisions, bugs, and context. Returns recent and relevant memories. Use memory_search for specific topics."""


def handle_memory_save(
    service: MemoryService,
    title: str,
    what: str,
    why: Optional[str] = None,
    impact: Optional[str] = None,
    tags: Optional[list[str]] = None,
    category: Optional[str] = None,
    related_files: Optional[list[str]] = None,
    details: Optional[str] = None,
    project: Optional[str] = None,
) -> str:
    """Handle memory_save tool call. Returns JSON string."""
    project = project or os.path.basename(os.getcwd())

    if category and category not in VALID_CATEGORIES:
        category = "context"

    raw = RawMemoryInput(
        title=title[:60],
        what=what,
        why=why,
        impact=impact,
        tags=tags or [],
        category=category,
        related_files=related_files or [],
        details=details,
    )

    result = service.save(raw, project=project)
    return json.dumps(result)


def handle_memory_search(
    service: MemoryService,
    query: str,
    limit: int = 5,
    project: Optional[str] = None,
) -> str:
    """Handle memory_search tool call. Returns JSON string."""
    results = service.search(query, limit=limit, project=project)

    clean = []
    for r in results:
        tags_raw = r.get("tags", "[]")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []

        clean.append({
            "id": r["id"],
            "title": r["title"],
            "what": r["what"],
            "why": r.get("why"),
            "impact": r.get("impact"),
            "category": r.get("category"),
            "tags": tags_list,
            "project": r.get("project"),
            "created_at": r.get("created_at", "")[:10],
            "score": round(r.get("score", 0), 2),
            "has_details": bool(r.get("has_details")),
        })
    return json.dumps(clean)


def handle_memory_context(
    service: MemoryService,
    project: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Handle memory_context tool call. Returns JSON string."""
    project = project or os.path.basename(os.getcwd())

    results, total = service.get_context(
        limit=limit,
        project=project,
        semantic_mode="never",
    )

    memories = []
    for r in results:
        tags_raw = r.get("tags", "[]")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []

        date_str = r.get("created_at", "")[:10]
        try:
            dt = datetime.fromisoformat(date_str)
            date_display = dt.strftime("%b %d")
        except (ValueError, TypeError):
            date_display = date_str

        memories.append({
            "id": r["id"],
            "title": r.get("title", "Untitled"),
            "category": r.get("category", ""),
            "tags": tags_list,
            "date": date_display,
        })

    return json.dumps({
        "total": total,
        "showing": len(memories),
        "memories": memories,
        "message": "Use memory_search for specific topics. Use memory_save to persist decisions and discoveries.",
    })


def _create_server(service: MemoryService) -> Server:
    """Create and configure the MCP server with memory tools."""
    server = Server("echovault")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="memory_save",
                description=SAVE_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title, max 60 chars."},
                        "what": {"type": "string", "description": "1-2 sentences. The essence a future agent needs."},
                        "why": {"type": "string", "description": "Reasoning behind the decision or fix."},
                        "impact": {"type": "string", "description": "What changed as a result."},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Relevant tags."},
                        "category": {
                            "type": "string",
                            "enum": list(VALID_CATEGORIES),
                            "description": "decision: chose X over Y. bug: fixed a problem. pattern: reusable gotcha. learning: non-obvious discovery. context: project setup/architecture.",
                        },
                        "related_files": {"type": "array", "items": {"type": "string"}, "description": "File paths involved."},
                        "details": {"type": "string", "description": "Full context for a future agent with zero context."},
                        "project": {"type": "string", "description": "Project name. Auto-detected from cwd if omitted."},
                    },
                    "required": ["title", "what"],
                },
            ),
            Tool(
                name="memory_search",
                description=SEARCH_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search terms"},
                        "limit": {"type": "integer", "default": 5, "description": "Max results"},
                        "project": {"type": "string", "description": "Filter to project."},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="memory_context",
                description=CONTEXT_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project name. Auto-detected from cwd if omitted."},
                        "limit": {"type": "integer", "default": 10, "description": "Max memories"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "memory_save":
            result = handle_memory_save(service, **arguments)
        elif name == "memory_search":
            result = handle_memory_search(service, **arguments)
        elif name == "memory_context":
            result = handle_memory_context(service, **arguments)
        else:
            result = json.dumps({"error": f"Unknown tool: {name}"})

        return [TextContent(type="text", text=result)]

    return server


async def run_server():
    """Run the MCP server with stdio transport."""
    service = MemoryService()
    try:
        server = _create_server(service)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        service.close()
