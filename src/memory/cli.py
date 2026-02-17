"""CLI commands for the memory system.

This module provides the command-line interface for managing memories.
All commands use the MemoryService for business logic.
"""

import os
from dataclasses import asdict

import yaml

import click

from memory.config import get_memory_home, load_config
from memory.core import MemoryService
from memory.models import RawMemoryInput


def _redact_api_keys(data: dict) -> dict:
    for section in ("embedding",):
        config = data.get(section)
        if isinstance(config, dict) and config.get("api_key"):
            config["api_key"] = "<redacted>"
    return data


@click.group()
def main():
    """Memory — local memory for coding agents."""
    pass


@main.command()
def init():
    """Initialize the memory vault."""
    home = get_memory_home()
    vault_dir = os.path.join(home, "vault")
    os.makedirs(vault_dir, exist_ok=True)
    click.echo(f"Memory vault initialized at {home}")


@main.group(invoke_without_command=True)
@click.pass_context
def config(ctx):
    """Show or manage configuration."""
    if ctx.invoked_subcommand is None:
        home = get_memory_home()
        cfg = load_config(os.path.join(home, "config.yaml"))
        data = _redact_api_keys(asdict(cfg))
        data["memory_home"] = home
        click.echo(yaml.safe_dump(data, sort_keys=False))


_CONFIG_TEMPLATE = """\
# EchoVault configuration
# Docs: https://github.com/mraza007/echovault#configure-embeddings-optional

# Embedding provider for semantic search.
# Without this, keyword search (FTS5) still works.
embedding:
  provider: ollama              # ollama | openai
  model: nomic-embed-text
  # api_key: sk-...            # required for openai

# How memories are retrieved at session start.
# "auto" uses vectors when available, falls back to keywords.
context:
  semantic: auto                # auto | always | never
  topup_recent: true            # also include recent memories
"""


@config.command("init")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing config")
def config_init(force):
    """Generate a starter config.yaml."""
    home = get_memory_home()
    config_path = os.path.join(home, "config.yaml")

    if os.path.exists(config_path) and not force:
        click.echo(f"Config already exists at {config_path}")
        click.echo("Use --force to overwrite.")
        return

    os.makedirs(home, exist_ok=True)
    with open(config_path, "w") as f:
        f.write(_CONFIG_TEMPLATE)

    click.echo(f"Created {config_path}")
    click.echo("Edit the file to configure your embedding provider.")


@main.command()
@click.option("--title", required=True, help="Title of the memory")
@click.option("--what", required=True, help="What happened or was learned")
@click.option("--why", default=None, help="Why it matters")
@click.option("--impact", default=None, help="Impact or consequences")
@click.option("--tags", default="", help="Comma-separated tags")
@click.option(
    "--category",
    type=click.Choice(["decision", "pattern", "bug", "context", "learning"]),
    default=None,
    help="Category of the memory",
)
@click.option("--related-files", default="", help="Comma-separated file paths")
@click.option("--details", default=None, help="Extended details or context")
@click.option("--source", default=None, help="Source of the memory")
@click.option("--project", default=None, help="Project name")
def save(title, what, why, impact, tags, category, related_files, details, source, project):
    """Save a memory to the current session."""
    project = project or os.path.basename(os.getcwd())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    file_list = [f.strip() for f in related_files.split(",") if f.strip()] if related_files else []

    raw = RawMemoryInput(
        title=title,
        what=what,
        why=why,
        impact=impact,
        tags=tag_list,
        category=category,
        related_files=file_list,
        details=details,
        source=source,
    )

    svc = MemoryService()
    result = svc.save(raw, project=project)
    svc.close()

    click.echo(f"Saved: {title} (id: {result['id']})")
    click.echo(f"File: {result['file_path']}")


@main.command()
@click.argument("query")
@click.option("--limit", default=5, help="Maximum number of results")
@click.option(
    "--project",
    is_flag=True,
    default=False,
    help="Filter to current project (current directory name)",
)
@click.option("--source", default=None, help="Filter by source")
def search(query, limit, project, source):
    """Search memories using hybrid FTS5 + semantic search."""
    project_name = os.path.basename(os.getcwd()) if project else None

    svc = MemoryService()
    results = svc.search(query, limit=limit, project=project_name, source=source)
    svc.close()

    if not results:
        click.echo("No results found.")
        return

    click.echo(f"\n Results ({len(results)} found) ")

    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        cat = r.get("category", "")
        proj = r.get("project", "")
        src = r.get("source", "")
        has_details = r.get("has_details", False)

        click.echo(f"\n [{i}] {r['title']} (score: {score:.2f})")
        click.echo(f"     {cat} | {r.get('created_at', '')[:10]} | {proj}" + (f" | {src}" if src else ""))
        click.echo(f"     What: {r['what']}")

        if r.get("why"):
            click.echo(f"     Why: {r['why']}")

        if r.get("impact"):
            click.echo(f"     Impact: {r['impact']}")

        if has_details:
            click.echo(f"     Details: available (use `memory details {r['id'][:12]}`)")


@main.command()
@click.argument("memory_id")
def details(memory_id):
    """Fetch full details for a specific memory."""
    svc = MemoryService()
    detail = svc.get_details(memory_id)
    svc.close()

    if not detail:
        click.echo(f"No details found for memory {memory_id}")
        return

    click.echo(detail.body)


@main.command()
@click.argument("memory_id")
def delete(memory_id):
    """Delete a memory by ID or prefix."""
    svc = MemoryService()
    deleted = svc.delete(memory_id)
    svc.close()

    if deleted:
        click.echo(f"Deleted memory {memory_id}")
    else:
        click.echo(f"No memory found for {memory_id}")


@main.command()
@click.option(
    "--project",
    is_flag=True,
    default=False,
    help="Filter to current project (current directory name)",
)
@click.option("--source", default=None, help="Filter by source")
@click.option("--limit", default=10, help="Maximum number of pointers")
@click.option("--query", default=None, help="Semantic search query for filtering")
@click.option(
    "--semantic",
    "semantic_mode",
    flag_value="always",
    default=None,
    help="Force semantic search (embeddings)",
)
@click.option(
    "--fts-only",
    "semantic_mode",
    flag_value="never",
    help="Disable embeddings and use FTS-only",
)
@click.option(
    "--show-config",
    is_flag=True,
    default=False,
    help="Show effective configuration and exit",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["hook", "agents-md"]),
    default="hook",
    help="Output format",
)
def context(project, source, limit, query, semantic_mode, show_config, output_format):
    """Output memory pointers for agent context injection."""
    import json

    if show_config:
        home = get_memory_home()
        cfg = load_config(os.path.join(home, "config.yaml"))
        data = _redact_api_keys(asdict(cfg))
        data["memory_home"] = home
        click.echo(yaml.safe_dump(data, sort_keys=False))
        return

    project_name = os.path.basename(os.getcwd()) if project else None

    svc = MemoryService()
    results, total = svc.get_context(
        limit=limit,
        project=project_name,
        source=source,
        query=query,
        semantic_mode=semantic_mode,
    )
    svc.close()

    if not results:
        click.echo("No memories found.")
        return

    showing = len(results)

    if output_format == "agents-md":
        click.echo("## Memory Context\n")

    click.echo(f"Available memories ({total} total, showing {showing}):")

    for r in results:
        date_str = r.get("created_at", "")[:10]
        # Format date as "Mon DD" if possible
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(date_str)
            date_display = dt.strftime("%b %d")
        except (ValueError, TypeError):
            date_display = date_str

        title = r.get("title", "Untitled")
        cat = r.get("category", "")
        tags_raw = r.get("tags", "")
        if isinstance(tags_raw, str) and tags_raw:
            try:
                tags_list = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []

        cat_part = f" [{cat}]" if cat else ""
        tags_part = f" [{','.join(tags_list)}]" if tags_list else ""

        click.echo(f"- [{date_display}] {title}{cat_part}{tags_part}")

    if output_format == "agents-md":
        click.echo("")
    click.echo('Use `memory search <query>` for full details on any memory.')


@main.command()
def reindex():
    """Rebuild vector index with current embedding provider."""
    svc = MemoryService()

    total = svc.db.count_memories()
    if total == 0:
        click.echo("No memories to reindex.")
        svc.close()
        return

    click.echo(f"Reindexing {total} memories with {svc.config.embedding.provider}/{svc.config.embedding.model}...")

    def progress(current, count):
        click.echo(f"  {current}/{count}", nl=(current == count))
        if current < count:
            click.echo("\r", nl=False)

    result = svc.reindex(progress_callback=progress)
    svc.close()

    click.echo(
        f"Re-indexed {result['count']} memories with "
        f"{result['model']} ({result['dim']} dims)"
    )


@main.command()
@click.option("--limit", default=10, help="Maximum number of sessions to show")
@click.option("--project", default=None, help="Filter by project name")
def sessions(limit, project):
    """List recent sessions."""
    svc = MemoryService()
    vault = svc.vault_dir
    session_files = []

    if os.path.exists(vault):
        for proj_dir in sorted(os.listdir(vault)):
            proj_path = os.path.join(vault, proj_dir)
            if not os.path.isdir(proj_path) or proj_dir.startswith("."):
                continue
            if project and proj_dir != project:
                continue

            for f in sorted(os.listdir(proj_path), reverse=True):
                if f.endswith("-session.md"):
                    session_files.append((proj_dir, f))

    svc.close()

    if not session_files:
        click.echo("No sessions found.")
        return

    click.echo("\nSessions:")
    for proj, fname in session_files[:limit]:
        date_str = fname.replace("-session.md", "")
        click.echo(f"  {date_str} | {proj}")


def _resolve_config_dir(agent_dot_dir: str, config_dir: str | None, project: bool) -> str:
    """Resolve the config directory for an agent.

    Args:
        agent_dot_dir: The dot-directory name (e.g. ".claude", ".cursor", ".codex").
        config_dir: Explicit --config-dir override (takes priority).
        project: If True, use cwd; if False, use home directory.
    """
    if config_dir:
        return config_dir
    if project:
        return os.path.join(os.getcwd(), agent_dot_dir)
    return os.path.join(os.path.expanduser("~"), agent_dot_dir)


@main.group()
def setup():
    """Install EchoVault hooks for an agent."""
    pass


@setup.command("claude-code")
@click.option("--config-dir", default=None, help="Path to .claude directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_claude_code_cmd(config_dir, project):
    """Install hooks into Claude Code settings."""
    from memory.setup import setup_claude_code

    target = _resolve_config_dir(".claude", config_dir, project)
    result = setup_claude_code(target, project=project)
    click.echo(result["message"])


@setup.command("cursor")
@click.option("--config-dir", default=None, help="Path to .cursor directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_cursor_cmd(config_dir, project):
    """Install hooks into Cursor hooks.json."""
    from memory.setup import setup_cursor

    target = _resolve_config_dir(".cursor", config_dir, project)
    result = setup_cursor(target)
    click.echo(result["message"])


@setup.command("codex")
@click.option("--config-dir", default=None, help="Path to .codex directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_codex_cmd(config_dir, project):
    """Install EchoVault section into Codex AGENTS.md and config.toml."""
    from memory.setup import setup_codex

    target = _resolve_config_dir(".codex", config_dir, project)
    result = setup_codex(target)
    click.echo(result["message"])


@setup.command("opencode")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_opencode_cmd(project):
    """Install EchoVault MCP server into OpenCode."""
    from memory.setup import setup_opencode

    result = setup_opencode(project=project)
    click.echo(result["message"])


@main.group()
def uninstall():
    """Remove EchoVault hooks for an agent."""
    pass


@uninstall.command("claude-code")
@click.option("--config-dir", default=None, help="Path to .claude directory")
@click.option("--project", is_flag=True, default=False, help="Uninstall from current project instead of globally")
def uninstall_claude_code_cmd(config_dir, project):
    """Remove hooks from Claude Code settings."""
    from memory.setup import uninstall_claude_code

    target = _resolve_config_dir(".claude", config_dir, project)
    result = uninstall_claude_code(target, project=project)
    click.echo(result["message"])


@uninstall.command("cursor")
@click.option("--config-dir", default=None, help="Path to .cursor directory")
@click.option("--project", is_flag=True, default=False, help="Uninstall from current project instead of globally")
def uninstall_cursor_cmd(config_dir, project):
    """Remove hooks from Cursor hooks.json."""
    from memory.setup import uninstall_cursor

    target = _resolve_config_dir(".cursor", config_dir, project)
    result = uninstall_cursor(target)
    click.echo(result["message"])


@uninstall.command("codex")
@click.option("--config-dir", default=None, help="Path to .codex directory")
@click.option("--project", is_flag=True, default=False, help="Uninstall from current project instead of globally")
def uninstall_codex_cmd(config_dir, project):
    """Remove EchoVault from Codex AGENTS.md and config.toml."""
    from memory.setup import uninstall_codex

    target = _resolve_config_dir(".codex", config_dir, project)
    result = uninstall_codex(target)
    click.echo(result["message"])


@uninstall.command("opencode")
@click.option("--project", is_flag=True, default=False, help="Uninstall from current project instead of globally")
def uninstall_opencode_cmd(project):
    """Remove EchoVault from OpenCode."""
    from memory.setup import uninstall_opencode

    result = uninstall_opencode(project=project)
    click.echo(result["message"])


@main.command()
def mcp():
    """Start the EchoVault MCP server (stdio transport)."""
    import asyncio
    from memory.mcp_server import run_server

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
