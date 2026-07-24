"""CLI commands for the memory system.

This module provides the command-line interface for managing memories.
All commands use the MemoryService for business logic.
"""

import os
import shutil
from dataclasses import asdict

import yaml

import click

from memory.config import (
    clear_persisted_memory_home,
    get_memory_home,
    load_config,
    resolve_memory_home,
    set_persisted_memory_home,
    resolve_context_mode,
)
from memory.core import MemoryService
from memory.models import RawMemoryInput

DETAILS_TEMPLATE = """\
Context:

Options considered:
- Option A:
- Option B:

Decision:

Tradeoffs:

Follow-up:
"""


def _redact_api_keys(data: dict) -> dict:
    for section in ("embedding",):
        config = data.get(section)
        if isinstance(config, dict) and config.get("api_key"):
            config["api_key"] = "<redacted>"
    return data


@click.group()
@click.version_option(package_name="echovault", prog_name="echovault")
def main():
    """Memory — local memory for coding agents."""
    pass


def _initialize_vault() -> tuple[str, bool]:
    """Create the vault directory and report whether it was newly created."""
    home = get_memory_home()
    vault_dir = os.path.join(home, "vault")
    created = not os.path.isdir(vault_dir)
    os.makedirs(vault_dir, exist_ok=True)
    return home, created


@main.command()
def init():
    """Initialize the memory vault."""
    home, _ = _initialize_vault()
    click.echo(f"Memory vault initialized at {home}")


@main.group(invoke_without_command=True)
@click.pass_context
def config(ctx):
    """Show or manage configuration."""
    if ctx.invoked_subcommand is None:
        home, source = resolve_memory_home()
        cfg = load_config(os.path.join(home, "config.yaml"))
        data = _redact_api_keys(asdict(cfg))
        data["memory_home"] = home
        data["memory_home_source"] = source
        click.echo(yaml.safe_dump(data, sort_keys=False))


@config.command("set-home")
@click.argument("path")
def config_set_home(path):
    """Persist memory home location (used when MEMORY_HOME is unset)."""
    resolved = set_persisted_memory_home(path)
    os.makedirs(resolved, exist_ok=True)
    os.makedirs(os.path.join(resolved, "vault"), exist_ok=True)
    click.echo(f"Persisted memory home: {resolved}")
    click.echo("Override anytime with MEMORY_HOME.")


@config.command("clear-home")
def config_clear_home():
    """Remove persisted memory home location from global config."""
    changed = clear_persisted_memory_home()
    if changed:
        click.echo("Cleared persisted memory home setting.")
    else:
        click.echo("No persisted memory home setting was found.")


_CONFIG_TEMPLATE = """\
# EchoVault configuration
# Docs: https://github.com/mraza007/echovault#configure-embeddings-optional

# Embedding provider for semantic search.
# Without this, keyword search (FTS5) still works.
embedding:
  provider: ollama              # ollama | openai
  model: nomic-embed-text
  # base_url: http://localhost:11434   # ollama default; for openai: https://api.openai.com/v1
  # api_key: sk-...            # required for openai

# How memories are retrieved at session start.
# "auto" uses vectors when available, falls back to keywords.
context:
  mode: auto                    # on | off | auto
  semantic: auto                # auto | always | never
  topup_recent: true            # also include recent memories
  token_budget: 1200            # approximate injected-context budget
  min_relevance: 0.70           # real-world nomic benchmark default
  min_vector_similarity: 0.05   # nomic-embed-text default; calibrate per model
  agent_modes: {}               # e.g. {codex: on, claude-code: off}
"""


def _write_context_mode(mode: str, agent: str | None = None) -> None:
    home = get_memory_home()
    path = os.path.join(home, "config.yaml")
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        data = {}
    context_data = data.setdefault("context", {})
    if agent:
        context_data.setdefault("agent_modes", {})[agent] = mode
    else:
        context_data["mode"] = mode
    os.makedirs(home, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)


@config.command("context")
@click.argument("mode", required=False, type=click.Choice(["on", "off", "auto"]))
@click.option("--agent", default=None, help="Set or inspect an agent-specific policy")
def config_context(mode, agent):
    """Show or set automatic agent-context policy."""
    if mode:
        _write_context_mode(mode, agent)
    cfg = load_config(os.path.join(get_memory_home(), "config.yaml"))
    effective, source = resolve_context_mode(cfg, agent)
    click.echo(f"context: {effective} ({source})")


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
    type=click.Choice([
        "decision", "pattern", "bug", "context", "learning", "playbook",
        "known_fix", "constraint", "project_state", "active_work",
    ]),
    default=None,
    help="Category of the memory",
)
@click.option("--related-files", default="", help="Comma-separated file paths")
@click.option("--details", default=None, help="Extended details or context")
@click.option("--details-file", default=None, help="Path to a file containing extended details")
@click.option("--details-template", is_flag=True, default=False, help="Use a structured details template")
@click.option("--source", default=None, help="Source of the memory")
@click.option("--project", default=None, help="Project name")
@click.option("--triggers", default="", help="Comma-separated playbook triggers")
@click.option("--prerequisites", default="", help="Comma-separated prerequisites")
@click.option("--steps", default="", help="Pipe-separated procedure steps")
@click.option("--verification", default="", help="Pipe-separated verification commands")
@click.option("--follow-ups", default="", help="Pipe-separated follow-ups")
@click.option("--constraints", default="", help="Pipe-separated constraints")
@click.option("--alternatives-rejected", default="", help="Pipe-separated rejected alternatives")
@click.option("--open-questions", default="", help="Pipe-separated open questions")
@click.option("--confidence", type=click.FloatRange(0.0, 1.0), default=None)
@click.option("--valid-from", default=None, help="ISO date/time when valid")
@click.option("--valid-until", default=None, help="ISO date/time expiry")
@click.option("--commit-sha", default=None)
@click.option("--branch", default=None)
@click.option("--links", default="", help="Comma-separated provenance links")
@click.option("--last-verified", default=None, help="ISO date/time last verified")
def save(
    title,
    what,
    why,
    impact,
    tags,
    category,
    related_files,
    details,
    details_file,
    details_template,
    source,
    project,
    triggers, prerequisites, steps, verification, follow_ups, constraints, alternatives_rejected,
    open_questions, confidence, valid_from, valid_until, commit_sha, branch,
    links, last_verified,
):
    """Save a memory to the current session."""
    project = project or os.path.basename(os.getcwd())
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    file_list = [f.strip() for f in related_files.split(",") if f.strip()] if related_files else []

    if details and details_file:
        raise click.UsageError("Use either --details or --details-file, not both.")

    resolved_details = details
    if details_file:
        try:
            with open(details_file) as f:
                resolved_details = f.read()
        except OSError as e:
            raise click.ClickException(f"Failed to read details file '{details_file}': {e}") from e

    if details_template and not (resolved_details or "").strip():
        resolved_details = DETAILS_TEMPLATE

    raw = RawMemoryInput(
        title=title,
        what=what,
        why=why,
        impact=impact,
        tags=tag_list,
        category=category,
        related_files=file_list,
        details=resolved_details,
        source=source,
        triggers=[v.strip() for v in triggers.split(",") if v.strip()],
        prerequisites=[v.strip() for v in prerequisites.split(",") if v.strip()],
        steps=[v.strip() for v in steps.split("|") if v.strip()],
        verification=[v.strip() for v in verification.split("|") if v.strip()],
        follow_ups=[v.strip() for v in follow_ups.split("|") if v.strip()],
        constraints=[v.strip() for v in constraints.split("|") if v.strip()],
        alternatives_rejected=[v.strip() for v in alternatives_rejected.split("|") if v.strip()],
        open_questions=[v.strip() for v in open_questions.split("|") if v.strip()],
        confidence=confidence, valid_from=valid_from, valid_until=valid_until,
        commit_sha=commit_sha, branch=branch,
        links=[v.strip() for v in links.split(",") if v.strip()],
        last_verified=last_verified,
    )

    svc = MemoryService()
    result = svc.save(raw, project=project)
    svc.close()

    click.echo(f"Saved: {title} (id: {result['id']})")
    click.echo(f"File: {result['file_path']}")
    for warning in result.get("warnings", []):
        click.echo(f"Warning: {warning}")


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
@click.option("--explain", is_flag=True, help="Show raw ranking diagnostics")
def search(query, limit, project, source, explain):
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
        if explain:
            click.echo("     Ranking: " + yaml.safe_dump(r.get("score_explain", {"mode": "fallback", "score": score}), default_flow_style=True).strip())


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
@click.option("--agent", default=None, help="Agent name for policy override")
@click.option("--token-budget", type=int, default=None, help="Approximate context token budget")
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
def context(project, source, limit, query, agent, token_budget, semantic_mode, show_config, output_format):
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
    policy = svc.context_policy(agent)
    if not policy["enabled"]:
        click.echo(f"Automatic memory context is disabled ({policy['source']}).")
        svc.close()
        return
    results, total = svc.get_context(
        limit=limit,
        project=project_name,
        source=source,
        query=query,
        semantic_mode=semantic_mode,
        agent=agent,
        token_budget=token_budget,
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
        if query and r.get("what"):
            click.echo(f"  {r['what']}")

    if output_format == "agents-md":
        click.echo("")
    click.echo('Use `memory search <query>` for full details on any memory.')


@main.command("evaluate")
@click.argument("golden_set", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", default=5)
@click.option("--project", default=None)
@click.option("--sweep", is_flag=True, help="Calibrate relevance thresholds over a standard grid")
@click.option("--min-recall", default=1.0, type=click.FloatRange(0.0, 1.0), help="Minimum recall required for sweep recommendations")
@click.option("--max-negative-fpr", default=0.0, type=click.FloatRange(0.0, 1.0), help="Maximum unrelated-query false-positive rate")
@click.option("--min-relevance", default=None, type=click.FloatRange(0.0, 1.0), help="Temporarily override ranked-result threshold")
@click.option("--min-vector-similarity", default=None, type=click.FloatRange(0.0, 1.0), help="Temporarily override vector threshold")
def evaluate_cmd(golden_set, limit, project, sweep, min_recall, max_negative_fpr, min_relevance, min_vector_similarity):
    """Evaluate retrieval against a redacted YAML golden set."""
    from memory.evaluation import evaluate, load_golden_set, sweep_thresholds
    svc = MemoryService()
    cases = load_golden_set(golden_set)
    if min_relevance is not None:
        svc.config.context.min_relevance = min_relevance
    if min_vector_similarity is not None:
        svc.config.context.min_vector_similarity = min_vector_similarity
    report = (
        sweep_thresholds(
            svc, cases, limit=limit, project=project,
            min_recall=min_recall, max_negative_fpr=max_negative_fpr,
        )
        if sweep else evaluate(svc, cases, limit=limit, project=project)
    )
    svc.close()
    click.echo(yaml.safe_dump(report, sort_keys=False))


@main.command("feedback")
@click.argument("event", type=click.Choice(["referenced", "dismissed"]))
@click.argument("memory_ids", nargs=-1, required=True)
def feedback_cmd(event, memory_ids):
    """Record local retrieval feedback for one or more memories."""
    svc = MemoryService()
    count = svc.db.record_feedback(list(memory_ids), event)
    svc.close()
    click.echo(f"Recorded {event} for {count} memories.")


@main.command("review")
@click.option("--project", default=None)
def review_cmd(project):
    """Propose lifecycle cleanup without changing memories."""
    from memory.health import lifecycle_review
    svc = MemoryService()
    report = lifecycle_review(svc.db, project)
    svc.close()
    click.echo(yaml.safe_dump(report, sort_keys=False))


@main.command("doctor")
@click.option("--project", default=None)
def doctor_cmd(project):
    """Check vault, index, vectors, references, and lifecycle health."""
    from memory.health import doctor
    svc = MemoryService()
    report = doctor(svc, project)
    svc.close()
    click.echo(yaml.safe_dump(report, sort_keys=False))


@main.command("import")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be imported without changing anything")
@click.option("--reindex", "do_reindex", is_flag=True, default=False, help="Run reindex after importing")
def import_vault(dry_run, do_reindex):
    """Import memories from vault markdown files into the local index.

    Scans all .md files in vault/ sub-directories, parses H3 memory
    sections, and inserts any that are missing from the local SQLite
    database.  Useful in multi-agent setups where new files arrive
    via file-sync (e.g. Syncthing) but are not yet indexed.

    Deduplication is by (project, file_path, section_anchor) — existing memories are skipped.
    """
    svc = MemoryService()

    if dry_run:
        click.echo("Dry run — no changes will be made.\n")

    def progress(imported, skipped, project, title):
        if dry_run:
            click.echo(f"  [new] {project}/{title}")

    result = svc.import_from_vault(dry_run=dry_run, progress_callback=progress)

    click.echo(f"\nImported: {result['imported']}, Skipped (already exists): {result['skipped']}")
    if result["projects"]:
        click.echo(f"Projects with new imports: {', '.join(result['projects'])}")

    if do_reindex and result["imported"] > 0 and not dry_run:
        total = svc.db.count_memories()
        click.echo(f"\nReindexing {total} memories with {svc.config.embedding.provider}/{svc.config.embedding.model}...")

        def reindex_progress(current, count):
            click.echo(f"  {current}/{count}", nl=(current == count))
            if current < count:
                click.echo("\r", nl=False)

        reindex_result = svc.reindex(progress_callback=reindex_progress)
        click.echo(
            f"Re-indexed {reindex_result['count']} memories with "
            f"{reindex_result['model']} ({reindex_result['dim']} dims)"
        )

    svc.close()


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


@main.command()
@click.option("--project", default=None, help="Initial project filter for the dashboard")
@click.option("--include-archived", is_flag=True, default=False, help="Show archived memories on launch")
def dashboard(project, include_archived):
    """Launch the EchoVault terminal dashboard."""
    import shutil

    binary = shutil.which("memory-dashboard")
    if binary is None:
        click.echo("Error: memory-dashboard binary not found on PATH.")
        click.echo("Build it: cd dashboard && cargo build --release")
        click.echo("Install it: cp dashboard/target/release/memory-dashboard ~/.local/bin/")
        raise SystemExit(1)

    cmd = [binary]
    if project:
        cmd.extend(["--project", project])
    if include_archived:
        cmd.append("--include-archived")

    memory_home = get_memory_home()
    os.environ["MEMORY_HOME"] = memory_home
    os.execvp(binary, cmd)


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


_AGENTS = {
    "claude-code": {"command": "claude", "config_dir": ".claude"},
    "cursor": {"command": "cursor", "config_dir": ".cursor"},
    "codex": {"command": "codex", "config_dir": ".codex"},
    "opencode": {"command": "opencode", "config_dir": ".config/opencode"},
}


def _detect_agents() -> list[str]:
    """Return supported agents that appear to be installed."""
    home = os.path.expanduser("~")
    detected = []
    for agent, metadata in _AGENTS.items():
        command_found = shutil.which(metadata["command"]) is not None
        config_found = os.path.exists(os.path.join(home, metadata["config_dir"]))
        if command_found or config_found:
            detected.append(agent)
    return detected


def _setup_agent(agent: str, *, project: bool) -> dict[str, str]:
    """Run setup for one supported agent using its default config location."""
    if agent == "claude-code":
        from memory.setup import setup_claude_code

        target = _resolve_config_dir(".claude", None, project)
        return setup_claude_code(target, project=project)
    if agent == "cursor":
        from memory.setup import setup_cursor

        target = _resolve_config_dir(".cursor", None, project)
        return setup_cursor(target)
    if agent == "codex":
        from memory.setup import setup_codex

        target = _resolve_config_dir(".codex", None, project)
        return setup_codex(target)
    if agent == "opencode":
        from memory.setup import setup_opencode

        return setup_opencode(project=project)
    raise click.ClickException(f"Unsupported agent: {agent}")


def _finish_setup(agent: str, result: dict[str, str]) -> None:
    """Print a consistent setup result and activation hint."""
    home, created = _initialize_vault()
    if created:
        click.echo(f"Initialized memory vault at {home}")
    click.echo(result["message"])
    click.echo(f"Ready. Restart {agent} to load EchoVault.")


@main.group(invoke_without_command=True)
@click.option(
    "--project",
    is_flag=True,
    default=False,
    help="Install in the current project instead of globally",
)
@click.pass_context
def setup(ctx, project):
    """Set up EchoVault for an agent.

    Run without a subcommand for guided setup, or select an agent directly:
    ``memory setup codex``.
    """
    if ctx.invoked_subcommand is not None:
        return

    detected = _detect_agents()
    choices = list(_AGENTS)

    if len(detected) == 1:
        agent = detected[0]
        click.echo(f"Detected {agent}.")
    else:
        if detected:
            click.echo(f"Detected: {', '.join(detected)}")
        else:
            click.echo("No supported agent was detected automatically.")
        agent = click.prompt(
            "Which agent should EchoVault configure?",
            type=click.Choice(choices, case_sensitive=False),
            show_choices=True,
        )

    result = _setup_agent(agent, project=project)
    _finish_setup(agent, result)


@setup.command("claude-code")
@click.option("--config-dir", default=None, help="Path to .claude directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_claude_code_cmd(config_dir, project):
    """Set up EchoVault for Claude Code."""
    from memory.setup import setup_claude_code

    target = _resolve_config_dir(".claude", config_dir, project)
    result = setup_claude_code(target, project=project)
    _finish_setup("claude-code", result)


@setup.command("cursor")
@click.option("--config-dir", default=None, help="Path to .cursor directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_cursor_cmd(config_dir, project):
    """Set up EchoVault for Cursor."""
    from memory.setup import setup_cursor

    target = _resolve_config_dir(".cursor", config_dir, project)
    result = setup_cursor(target)
    _finish_setup("cursor", result)


@setup.command("codex")
@click.option("--config-dir", default=None, help="Path to .codex directory")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_codex_cmd(config_dir, project):
    """Set up EchoVault for Codex."""
    from memory.setup import setup_codex

    target = _resolve_config_dir(".codex", config_dir, project)
    result = setup_codex(target)
    _finish_setup("codex", result)


@setup.command("opencode")
@click.option("--project", is_flag=True, default=False, help="Install in current project instead of globally")
def setup_opencode_cmd(project):
    """Set up EchoVault for OpenCode."""
    from memory.setup import setup_opencode

    result = setup_opencode(project=project)
    _finish_setup("opencode", result)


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
