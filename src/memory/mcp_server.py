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

VALID_CATEGORIES = (
    "decision", "bug", "pattern", "learning", "context", "playbook",
    "known_fix", "constraint", "project_state", "active_work",
)

SAVE_DESCRIPTION = """Save a memory for future sessions. You MUST call this before ending any session where you made changes, fixed bugs, made decisions, or learned something. This is not optional — failing to save means the next session starts from zero.

Save when you:
- Made an architectural or design decision (chose X over Y)
- Fixed a bug (include root cause and solution)
- Discovered a non-obvious pattern or gotcha
- Learned something about the codebase not obvious from code
- Set up infrastructure, tooling, or configuration
- The user corrected you or clarified a requirement

Do NOT save: trivial changes (typos, formatting), info obvious from reading the code, or duplicates of existing memories. Write for a future agent with zero context."""
SAVE_DESCRIPTION += """

When filling `details`, prefer this structure:
- Context
- Options considered
- Decision
- Tradeoffs
- Follow-up"""

SEARCH_DESCRIPTION = """Search memories using keyword and semantic search. Use this when the task-aware memory_context pack is insufficient or when investigating a narrower topic. Explicit search remains available even when automatic context is disabled."""

CONTEXT_DESCRIPTION = """Get a task-aware living-memory context pack for the current project. You MUST call this before feature development, planning, debugging, or architecture work. Pass the current user request verbatim or as a faithful task summary in `query`, and pass your runtime identity in `agent` (for example `claude-code` or `codex`) so policy overrides work. The response includes summaries, structured playbooks, constraints, provenance, and token estimates directly to avoid extra round trips. If policy reports disabled, continue without automatic context; explicit memory_search and memory_save still work."""


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
    triggers: Optional[list[str]] = None,
    prerequisites: Optional[list[str]] = None,
    steps: Optional[list[str]] = None,
    verification: Optional[list[str]] = None,
    follow_ups: Optional[list[str]] = None,
    constraints: Optional[list[str]] = None,
    alternatives_rejected: Optional[list[str]] = None,
    open_questions: Optional[list[str]] = None,
    confidence: Optional[float] = None,
    valid_from: Optional[str] = None,
    valid_until: Optional[str] = None,
    commit_sha: Optional[str] = None,
    branch: Optional[str] = None,
    links: Optional[list[str]] = None,
    last_verified: Optional[str] = None,
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
        triggers=triggers or [], prerequisites=prerequisites or [], steps=steps or [],
        verification=verification or [], follow_ups=follow_ups or [],
        constraints=constraints or [], open_questions=open_questions or [],
        alternatives_rejected=alternatives_rejected or [],
        confidence=confidence, valid_from=valid_from, valid_until=valid_until,
        commit_sha=commit_sha, branch=branch, links=links or [],
        last_verified=last_verified,
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
    query: Optional[str] = None,
    agent: Optional[str] = None,
    token_budget: Optional[int] = None,
) -> str:
    """Handle memory_context tool call. Returns JSON string."""
    project = project or os.path.basename(os.getcwd())

    policy = service.context_policy(agent)
    if not policy["enabled"]:
        return json.dumps({"total": service.db.count_memories(project=project), "showing": 0, "memories": [], "disabled": True, "policy": policy})
    results, total = service.get_context(
        limit=limit,
        project=project,
        query=query,
        agent=agent,
        token_budget=token_budget,
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
            "what": r.get("what"),
            "why": r.get("why"),
            "impact": r.get("impact"),
            "category": r.get("category", ""),
            "tags": tags_list,
            "date": date_display,
            "structured": json.loads(r.get("structured_data") or "{}") if isinstance(r.get("structured_data"), str) else (r.get("structured_data") or {}),
            "provenance": {
                key: r.get(key) for key in (
                    "confidence", "valid_from", "valid_until", "commit_sha",
                    "branch", "last_verified",
                ) if r.get(key) is not None
            },
            "estimated_tokens": r.get("estimated_tokens"),
        })

    return json.dumps({
        "total": total,
        "showing": len(memories),
        "memories": memories,
        "message": "Use memory_search for specific topics. IMPORTANT: You MUST call memory_save before this session ends if you make any changes, decisions, or discoveries.",
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
                        "details": {
                            "type": "string",
                            "description": (
                                "Full context for a future agent with zero context. "
                                "Prefer: Context, Options considered, Decision, Tradeoffs, Follow-up."
                            ),
                        },
                        "project": {"type": "string", "description": "Project name. Auto-detected from cwd if omitted."},
                        "triggers": {"type": "array", "items": {"type": "string"}},
                        "prerequisites": {"type": "array", "items": {"type": "string"}},
                        "steps": {"type": "array", "items": {"type": "string"}},
                        "verification": {"type": "array", "items": {"type": "string"}},
                        "follow_ups": {"type": "array", "items": {"type": "string"}},
                        "constraints": {"type": "array", "items": {"type": "string"}},
                        "alternatives_rejected": {"type": "array", "items": {"type": "string"}},
                        "open_questions": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "valid_from": {"type": "string"}, "valid_until": {"type": "string"},
                        "commit_sha": {"type": "string"}, "branch": {"type": "string"},
                        "links": {"type": "array", "items": {"type": "string"}},
                        "last_verified": {"type": "string"},
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
                        "query": {"type": "string", "description": "Required for task-aware work: the current user request or a faithful task summary."},
                        "agent": {"type": "string", "description": "Your runtime identity for policy overrides: claude-code, codex, cursor, or opencode."},
                        "token_budget": {"type": "integer", "default": 1200, "description": "Approximate context token budget."},
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
