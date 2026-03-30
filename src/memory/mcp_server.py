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

SEARCH_DESCRIPTION = """Search memories using keyword and semantic search. Returns matching memories ranked by relevance. You MUST call this at session start before doing any work, and whenever the user's request relates to a topic that may have prior context."""

CONTEXT_DESCRIPTION = """Get memory context for the current project. You MUST call this at session start to load prior decisions, bugs, and context. Do not skip this step — prior sessions contain decisions and context that directly affect your current task. Use memory_search for specific topics."""

RECORD_USAGE_DESCRIPTION = """Record usage of a memory entry. Use 'type=core' for Core Memories and 'type=main' for EchoVault memories. Recording usage is essential for the Memory Governor to move memories between layers."""

GOVERNOR_DESCRIPTION = """Run the Memory Governor to move memories between Core Memory and Main Memory based on usage statistics.
- Core -> Main: if not used for 10 sessions.
- Main -> Core: if used 3 times in a single session.
Returns a list of recommended actions (ADD/DELETE) for Core Memory."""

COLLECTIVE_DESCRIPTION = """Invoke the Collective Wisdom of Dwarh-cruisers when a single agent cannot solve a task.
Analyzes the task, searches all available memory projects, and suggests specialized tools or strategies.
Use this when search results are insufficient or the task requires cross-domain knowledge."""


def handle_memory_collective_solve(
    service: MemoryService,
    task_description: str,
) -> str:
    """Handle memory_collective_solve tool call. Returns JSON string with strategy."""
    # 1. Broad search across ALL projects in memory
    all_results = []
    try:
        # Search without project filter to get global context
        all_results = service.search(task_description, limit=10, project=None)
    except Exception:
        pass

    # 2. Identify relevant projects and patterns
    relevant_projects = sorted(list(set(r.get("project") for r in all_results if r.get("project"))))
    
    # 3. Analyze if we have specialized tools for this
    # (Simulated intelligence: if task involves 'network', suggest tcpdump/ip; 
    # if 'code', suggest ultracode graph tools)
    suggestions = []
    task_lower = task_description.lower()
    
    if any(k in task_lower for k in ["network", "ip", "port", "connection", "ssh"]):
        suggestions.append("Use 'tcpdump' or 'ss' for L3-L4 diagnostics.")
        suggestions.append("Check 'Consolidated SSH Access Map' in Core Memory.")
    
    if any(k in task_lower for k in ["refactor", "complexity", "dependency", "class", "function"]):
        suggestions.append("Invoke 'ultracode' for graph-based impact analysis.")
        suggestions.append("Use 'mcp_ultracode_suggest_refactoring' for specific entities.")

    if any(k in task_lower for k in ["docker", "container", "sdk", "build"]):
        suggestions.append("Check 'docker-windows-optimization' requirements in specs.")
        suggestions.append("Use 'wsl --shutdown' if file locking persists.")

    # 4. Formulate Collective Response
    response = {
        "status": "collective_sync",
        "relevant_knowledge_domains": relevant_projects,
        "top_memories": [
            {"title": r["title"], "project": r["project"], "id": r["id"]} 
            for r in all_results[:3]
        ],
        "strategic_suggestions": suggestions or ["Deep dive into project-specific specifications recommended."],
        "message": "The Collective of Dwarh-cruisers has analyzed the probability field. Voids detected, applying specialized subroutines."
    }

    return json.dumps(response)


def handle_memory_record_usage(
    service: MemoryService,
    usage_type: str,
    memory_id: str,
) -> str:
    """Handle memory_record_usage tool call. Returns JSON string."""
    if usage_type == "core":
        service.db.record_core_memory_usage(memory_id, service.session_id)
        return json.dumps({"status": "success", "message": f"Recorded usage for core memory {memory_id}"})
    elif usage_type == "main":
        service.db.record_access(memory_id, service.session_id)
        return json.dumps({"status": "success", "message": f"Recorded access for main memory {memory_id}"})
    return json.dumps({"status": "error", "message": f"Invalid usage type: {usage_type}"})


def handle_memory_governor(service: MemoryService) -> str:
    """Handle memory_governor tool call. Returns JSON string with actions."""
    session_id = service.session_id
    actions = []

    # 1. Demotion logic (Core -> Main)
    cursor = service.db.conn.cursor()
    cursor.execute("SELECT id, unused_sessions_count FROM core_memory_usage WHERE unused_sessions_count >= 10")
    to_demote = cursor.fetchall()
    for row in to_demote:
        actions.append({
            "action": "DELETE",
            "type": "core",
            "id": row["id"],
            "reason": f"Unused for {row['unused_sessions_count']} sessions"
        })

    # 2. Promotion logic (Main -> Core)
    cursor.execute("""
        SELECT id, title, what, why, impact, tags, category, project, session_access_count 
        FROM memories 
        WHERE last_session_id = ? AND session_access_count >= 3
    """, (session_id,))
    to_promote = cursor.fetchall()
    for row in to_promote:
        actions.append({
            "action": "ADD",
            "type": "core",
            "id": row["id"],
            "title": row["title"],
            "what": row["what"],
            "why": row["why"],
            "impact": row["impact"],
            "category": row["category"],
            "project": row["project"],
            "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
            "reason": f"Used {row['session_access_count']} times in current session"
        })

    # 3. Session End Maintenance
    service.db.increment_unused_sessions_for_core(session_id)
    
    # Generate next session ID
    import uuid
    new_sid = str(uuid.uuid4())
    service.db.set_meta("current_session_id", new_sid)

    return json.dumps({
        "actions": actions,
        "next_session_id": new_sid,
        "message": "Governor run complete. Please execute the recommended Core Memory actions."
    })


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
            Tool(
                name="memory_record_usage",
                description=RECORD_USAGE_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "usage_type": {"type": "string", "enum": ["core", "main"], "description": "Type of memory entry."},
                        "memory_id": {"type": "string", "description": "ID of the memory entry."},
                    },
                    "required": ["usage_type", "memory_id"],
                },
            ),
            Tool(
                name="memory_governor",
                description=GOVERNOR_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="memory_collective_solve",
                description=COLLECTIVE_DESCRIPTION,
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string", "description": "Description of the complex task."},
                    },
                    "required": ["task_description"],
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
        elif name == "memory_record_usage":
            result = handle_memory_record_usage(service, **arguments)
        elif name == "memory_governor":
            result = handle_memory_governor(service)
        elif name == "memory_collective_solve":
            result = handle_memory_collective_solve(service, **arguments)
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
