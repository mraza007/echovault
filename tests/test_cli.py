"""Tests for CLI commands."""

import os

from click.testing import CliRunner

from memory.cli import main
from memory.core import MemoryService
from memory.models import RawMemoryInput


def test_cli_help():
    """Test that memory --help shows help text."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Memory — local memory for coding agents." in result.output
    assert "init" in result.output
    assert "save" in result.output
    assert "search" in result.output
    assert "details" in result.output
    assert "sessions" in result.output


def test_init_creates_vault_dir(env_home):
    """Test that memory init creates the vault directory."""
    runner = CliRunner()
    result = runner.invoke(main, ["init"])

    assert result.exit_code == 0
    assert "Memory vault initialized at" in result.output
    assert str(env_home) in result.output

    # Verify vault directory was created
    vault_dir = os.path.join(str(env_home), "vault")
    assert os.path.exists(vault_dir)
    assert os.path.isdir(vault_dir)


def test_config_set_home_persists_path(tmp_path, monkeypatch):
    """Test that config set-home persists and creates the target structure."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEMORY_HOME", raising=False)

    target = tmp_path / "memory-store"
    runner = CliRunner()
    result = runner.invoke(main, ["config", "set-home", str(target)])

    assert result.exit_code == 0
    assert "Persisted memory home:" in result.output
    assert target.exists()
    assert (target / "vault").exists()


def test_config_clear_home_removes_setting(tmp_path, monkeypatch):
    """Test that config clear-home removes persisted home setting."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEMORY_HOME", raising=False)

    target = tmp_path / "memory-store"
    runner = CliRunner()
    set_result = runner.invoke(main, ["config", "set-home", str(target)])
    assert set_result.exit_code == 0

    clear_result = runner.invoke(main, ["config", "clear-home"])
    assert clear_result.exit_code == 0
    assert "Cleared persisted memory home setting." in clear_result.output


def test_config_show_includes_memory_home_source(tmp_path, monkeypatch):
    """Test that `memory config` shows memory_home_source metadata."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("MEMORY_HOME", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["config"])

    assert result.exit_code == 0
    assert "memory_home_source: default" in result.output


def test_save_with_required_fields_succeeds(env_home):
    """Test that memory save with required fields succeeds."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Test Memory",
            "--what", "Testing the save command",
        ],
    )

    assert result.exit_code == 0
    assert "Saved: Test Memory (id:" in result.output
    assert "File:" in result.output


def test_save_outputs_parseable_id(env_home):
    """Test that memory save outputs a parseable memory ID."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Memory with ID",
            "--what", "Testing ID output",
        ],
    )

    assert result.exit_code == 0

    # Extract ID from output
    lines = result.output.split("\n")
    saved_line = [line for line in lines if line.startswith("Saved:")][0]

    # Should contain "Saved: {title} (id: {uuid})"
    assert "Saved: Memory with ID (id:" in saved_line
    assert ")" in saved_line

    # Extract UUID (between "id: " and ")")
    id_part = saved_line.split("id: ")[1].split(")")[0]
    assert len(id_part) == 36  # UUID format


def test_save_with_all_fields(env_home):
    """Test that memory save with all fields succeeds."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Complete Memory",
            "--what", "Testing all fields",
            "--why", "To ensure completeness",
            "--impact", "Better test coverage",
            "--tags", "test,cli,complete",
            "--category", "decision",
            "--related-files", "test_cli.py,cli.py",
            "--details", "Extended details about this memory",
            "--source", "test-suite",
            "--project", "test-project",
        ],
    )

    assert result.exit_code == 0
    assert "Saved: Complete Memory (id:" in result.output


def test_save_with_details_template(env_home):
    """Test that --details-template scaffolds details when none provided."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Template Memory",
            "--what", "Testing details template",
            "--details-template",
            "--project", "test-project",
        ],
    )

    assert result.exit_code == 0

    # Extract saved memory ID from output
    saved_line = [line for line in result.output.split("\n") if line.startswith("Saved:")][0]
    memory_id = saved_line.split("id: ")[1].split(")")[0]

    service = MemoryService(memory_home=str(env_home))
    detail = service.get_details(memory_id)
    service.close()

    assert detail is not None
    assert "Context:" in detail.body
    assert "Options considered:" in detail.body
    assert "Decision:" in detail.body
    assert "Tradeoffs:" in detail.body
    assert "Follow-up:" in detail.body


def test_save_with_details_file(env_home, tmp_path):
    """Test that --details-file loads details from a file."""
    details_file = tmp_path / "details.txt"
    details_file.write_text(
        "Context:\nLoaded from file.\n\nOptions considered:\n- Use file input\n\nDecision:\nUse --details-file.\n\nTradeoffs:\nNeed file management.\n\nFollow-up:\nNone."
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "File Details Memory",
            "--what", "Testing details file",
            "--details-file", str(details_file),
            "--project", "test-project",
        ],
    )

    assert result.exit_code == 0

    saved_line = [line for line in result.output.split("\n") if line.startswith("Saved:")][0]
    memory_id = saved_line.split("id: ")[1].split(")")[0]

    service = MemoryService(memory_home=str(env_home))
    detail = service.get_details(memory_id)
    service.close()

    assert detail is not None
    assert "Loaded from file." in detail.body
    assert "Use --details-file." in detail.body


def test_save_rejects_details_and_details_file_together(env_home, tmp_path):
    """Test that --details and --details-file cannot be used together."""
    details_file = tmp_path / "details.txt"
    details_file.write_text("details from file")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Conflicting Details Input",
            "--what", "This should fail",
            "--details", "inline details",
            "--details-file", str(details_file),
        ],
    )

    assert result.exit_code != 0
    assert "Use either --details or --details-file" in result.output


def test_save_shows_details_warnings(env_home):
    """Test that save prints quality warnings for low-signal details."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Warning Memory",
            "--what", "Testing warning output",
            "--category", "decision",
            "--project", "test-project",
        ],
    )

    assert result.exit_code == 0
    assert "Warning:" in result.output
    assert "should include details" in result.output


def test_save_missing_required_field_fails(env_home):
    """Test that memory save without required fields fails."""
    runner = CliRunner()
    result = runner.invoke(main, ["save", "--title", "Missing What"])

    assert result.exit_code != 0
    assert "Missing option" in result.output or "required" in result.output.lower()


def test_save_uses_current_directory_as_project(env_home, monkeypatch):
    """Test that memory save uses current directory name as project by default."""
    # Set up a specific directory name
    test_dir = str(env_home / "my-test-project")
    os.makedirs(test_dir, exist_ok=True)
    monkeypatch.chdir(test_dir)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Auto Project Memory",
            "--what", "Testing auto project detection",
        ],
    )

    assert result.exit_code == 0

    # Verify the memory was saved to the correct project
    service = MemoryService(memory_home=str(env_home))
    results = service.search("Auto Project Memory", limit=1)
    service.close()

    assert len(results) == 1
    assert results[0]["project"] == "my-test-project"


def test_search_finds_saved_memories(env_home):
    """Test that memory search finds saved memories."""
    # Save a memory first
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="FastAPI Setup",
        what="Configured FastAPI with async routes",
        tags=["fastapi", "python"],
    )
    service.save(raw, project="test-project")
    service.close()

    # Search for it
    runner = CliRunner()
    result = runner.invoke(main, ["search", "FastAPI"])

    assert result.exit_code == 0
    assert "Results (1 found)" in result.output
    assert "FastAPI Setup" in result.output
    assert "Configured FastAPI with async routes" in result.output


def test_search_shows_score_and_metadata(env_home):
    """Test that memory search shows score and metadata."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Test Memory",
        what="Testing search output",
        category="decision",
    )
    service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["search", "search output"])

    assert result.exit_code == 0
    assert "score:" in result.output
    assert "decision" in result.output
    assert "test-project" in result.output


def test_search_with_limit_option(env_home):
    """Test that memory search respects --limit option."""
    service = MemoryService(memory_home=str(env_home))

    # Save multiple memories
    for i in range(10):
        raw = RawMemoryInput(
            title=f"Memory {i}",
            what="Common search term",
        )
        service.save(raw, project="test-project")
    service.close()

    # Search with limit
    runner = CliRunner()
    result = runner.invoke(main, ["search", "Common", "--limit", "3"])

    assert result.exit_code == 0
    # Should show only 3 results
    assert "Results (3 found)" in result.output or result.output.count("[1]") <= 3


def test_search_with_project_flag(env_home, monkeypatch):
    """Test that memory search --project scopes to current directory."""
    service = MemoryService(memory_home=str(env_home))

    # Save memories to different projects
    raw1 = RawMemoryInput(title="Project A Memory", what="In project A")
    service.save(raw1, project="project-a")

    raw2 = RawMemoryInput(title="Project B Memory", what="In project B")
    service.save(raw2, project="project-b")
    service.close()

    # Change to a directory with name matching project-a
    test_dir = str(env_home / "project-a")
    os.makedirs(test_dir, exist_ok=True)
    monkeypatch.chdir(test_dir)

    # Search with project flag
    runner = CliRunner()
    result = runner.invoke(main, ["search", "Memory", "--project"])

    assert result.exit_code == 0
    # Should only find project A memory
    assert "Project A Memory" in result.output
    assert "Project B Memory" not in result.output


def test_search_with_source_filter(env_home):
    """Test that memory search --source filters by source."""
    service = MemoryService(memory_home=str(env_home))

    # Save memories with different sources
    raw1 = RawMemoryInput(
        title="CLI Memory",
        what="From CLI",
        source="cli",
    )
    service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(
        title="Agent Memory",
        what="From agent",
        source="agent",
    )
    service.save(raw2, project="test-project")
    service.close()

    # Search with source filter
    runner = CliRunner()
    result = runner.invoke(main, ["search", "Memory", "--source", "cli"])

    assert result.exit_code == 0
    assert "CLI Memory" in result.output
    assert "Agent Memory" not in result.output


def test_search_no_results(env_home):
    """Test that memory search handles no results gracefully."""
    runner = CliRunner()
    result = runner.invoke(main, ["search", "nonexistent-query-xyz"])

    assert result.exit_code == 0
    assert "No results found." in result.output


def test_search_shows_details_hint(env_home):
    """Test that memory search shows hint for available details."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Memory with Details",
        what="Has extended details",
        details="This is the extended details section with more information.",
    )
    result = service.save(raw, project="test-project")
    memory_id = result["id"]
    service.close()

    runner = CliRunner()
    search_result = runner.invoke(main, ["search", "extended details"])

    assert search_result.exit_code == 0
    assert "Details: available" in search_result.output
    assert "memory details" in search_result.output
    assert memory_id[:12] in search_result.output


def test_details_returns_detail_text(env_home):
    """Test that memory details returns detail text."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Memory with Details",
        what="Short summary",
        details="Long detailed explanation with code examples and context.",
    )
    result = service.save(raw, project="test-project")
    memory_id = result["id"]
    service.close()

    runner = CliRunner()
    detail_result = runner.invoke(main, ["details", memory_id])

    assert detail_result.exit_code == 0
    assert "Long detailed explanation with code examples and context." in detail_result.output


def test_details_handles_nonexistent_id(env_home):
    """Test that memory details handles nonexistent ID gracefully."""
    runner = CliRunner()
    result = runner.invoke(main, ["details", "nonexistent-id-123"])

    assert result.exit_code == 0
    assert "No details found for memory nonexistent-id-123" in result.output


def test_details_handles_memory_without_details(env_home):
    """Test that memory details handles memories without details."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Memory without Details",
        what="No details provided",
    )
    result = service.save(raw, project="test-project")
    memory_id = result["id"]
    service.close()

    runner = CliRunner()
    detail_result = runner.invoke(main, ["details", memory_id])

    assert detail_result.exit_code == 0
    assert f"No details found for memory {memory_id}" in detail_result.output


def test_delete_removes_memory(env_home):
    """Test that memory delete removes a memory and confirms."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Memory to Delete",
        what="This will be deleted",
        details="Gone soon",
    )
    result = service.save(raw, project="test-project")
    memory_id = result["id"]
    service.close()

    runner = CliRunner()
    delete_result = runner.invoke(main, ["delete", memory_id])

    assert delete_result.exit_code == 0
    assert "Deleted" in delete_result.output


def test_delete_with_prefix(env_home):
    """Test that memory delete works with a UUID prefix."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(title="Prefix Delete", what="Delete by prefix")
    result = service.save(raw, project="test-project")
    prefix = result["id"][:8]
    service.close()

    runner = CliRunner()
    delete_result = runner.invoke(main, ["delete", prefix])

    assert delete_result.exit_code == 0
    assert "Deleted" in delete_result.output


def test_delete_nonexistent_id(env_home):
    """Test that memory delete handles nonexistent IDs."""
    runner = CliRunner()
    result = runner.invoke(main, ["delete", "nonexistent-id-123"])

    assert result.exit_code == 0
    assert "No memory found" in result.output


def test_sessions_lists_session_files(env_home):
    """Test that memory sessions lists session files."""
    # Create some session files
    vault_dir = os.path.join(str(env_home), "vault", "test-project")
    os.makedirs(vault_dir, exist_ok=True)

    # Create session files
    session1 = os.path.join(vault_dir, "2026-01-15-session.md")
    session2 = os.path.join(vault_dir, "2026-01-16-session.md")

    with open(session1, "w") as f:
        f.write("# Session 1\n")
    with open(session2, "w") as f:
        f.write("# Session 2\n")

    runner = CliRunner()
    result = runner.invoke(main, ["sessions"])

    assert result.exit_code == 0
    assert "Sessions:" in result.output
    assert "2026-01-15" in result.output
    assert "2026-01-16" in result.output
    assert "test-project" in result.output


def test_sessions_with_limit(env_home):
    """Test that memory sessions respects --limit option."""
    vault_dir = os.path.join(str(env_home), "vault", "test-project")
    os.makedirs(vault_dir, exist_ok=True)

    # Create multiple session files
    for i in range(10):
        session = os.path.join(vault_dir, f"2026-01-{i+1:02d}-session.md")
        with open(session, "w") as f:
            f.write(f"# Session {i}\n")

    runner = CliRunner()
    result = runner.invoke(main, ["sessions", "--limit", "3"])

    assert result.exit_code == 0
    # Count the number of session entries (each has a date and project)
    lines = [line for line in result.output.split("\n") if "test-project" in line]
    assert len(lines) <= 3


def test_sessions_with_project_filter(env_home):
    """Test that memory sessions --project filters by project."""
    # Create sessions for multiple projects
    vault_dir_a = os.path.join(str(env_home), "vault", "project-a")
    vault_dir_b = os.path.join(str(env_home), "vault", "project-b")
    os.makedirs(vault_dir_a, exist_ok=True)
    os.makedirs(vault_dir_b, exist_ok=True)

    session_a = os.path.join(vault_dir_a, "2026-01-15-session.md")
    session_b = os.path.join(vault_dir_b, "2026-01-16-session.md")

    with open(session_a, "w") as f:
        f.write("# Session A\n")
    with open(session_b, "w") as f:
        f.write("# Session B\n")

    runner = CliRunner()
    result = runner.invoke(main, ["sessions", "--project", "project-a"])

    assert result.exit_code == 0
    assert "project-a" in result.output
    assert "project-b" not in result.output


def test_sessions_no_sessions_found(env_home):
    """Test that memory sessions handles no sessions gracefully."""
    runner = CliRunner()
    result = runner.invoke(main, ["sessions"])

    assert result.exit_code == 0
    assert "No sessions found." in result.output


def test_save_with_comma_separated_tags(env_home):
    """Test that memory save correctly parses comma-separated tags."""
    import json

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Tagged Memory",
            "--what", "Testing tag parsing",
            "--tags", "python,fastapi,async",
        ],
    )

    assert result.exit_code == 0

    # Verify tags were saved correctly
    service = MemoryService(memory_home=str(env_home))
    results = service.search("Tagged Memory", limit=1)
    service.close()

    assert len(results) == 1
    # Tags are stored as JSON string in search results
    tags = json.loads(results[0].get("tags", "[]")) if results[0].get("tags") else []
    assert "python" in tags
    assert "fastapi" in tags
    assert "async" in tags


def test_save_with_comma_separated_files(env_home):
    """Test that memory save correctly parses comma-separated files."""
    import json

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Memory with Files",
            "--what", "Testing file parsing",
            "--related-files", "src/cli.py,tests/test_cli.py,README.md",
        ],
    )

    assert result.exit_code == 0

    # Verify files were saved correctly
    service = MemoryService(memory_home=str(env_home))
    results = service.search("Memory with Files", limit=1)
    service.close()

    assert len(results) == 1
    # Files are stored as JSON string in search results
    files = json.loads(results[0].get("related_files", "[]")) if results[0].get("related_files") else []
    assert "src/cli.py" in files
    assert "tests/test_cli.py" in files
    assert "README.md" in files


def test_save_invalid_category_fails(env_home):
    """Test that memory save with invalid category fails."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "save",
            "--title", "Bad Category",
            "--what", "Testing invalid category",
            "--category", "invalid-category",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value for '--category'" in result.output or "invalid choice" in result.output.lower()


# --- context command tests ---


def test_context_no_memories(env_home):
    """Test that memory context handles empty vault gracefully."""
    runner = CliRunner()
    result = runner.invoke(main, ["context"])

    assert result.exit_code == 0
    assert "No memories found." in result.output


def test_context_lists_recent_memories(env_home):
    """Test that memory context lists recent memories as pointers."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="JWT Token Rotation",
        what="Implemented refresh token rotation",
        category="decision",
        tags=["auth", "jwt"],
    )
    service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context"])

    assert result.exit_code == 0
    assert "Available memories (1 total, showing 1):" in result.output
    assert "JWT Token Rotation" in result.output
    assert "[decision]" in result.output
    assert "[auth,jwt]" in result.output


def test_context_with_project_flag(env_home, monkeypatch):
    """Test that memory context --project scopes to current directory."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(title="Project A Memory", what="In project A")
    service.save(raw1, project="project-a")

    raw2 = RawMemoryInput(title="Project B Memory", what="In project B")
    service.save(raw2, project="project-b")
    service.close()

    test_dir = str(env_home / "project-a")
    os.makedirs(test_dir, exist_ok=True)
    monkeypatch.chdir(test_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["context", "--project"])

    assert result.exit_code == 0
    assert "Project A Memory" in result.output
    assert "Project B Memory" not in result.output


def test_context_with_query(env_home):
    """Test that memory context --query filters by semantic search."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(
        title="Auth Token Setup",
        what="Configured JWT authentication tokens",
        tags=["auth"],
        category="decision",
    )
    service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(
        title="Database Migration",
        what="Migrated from MySQL to PostgreSQL",
        tags=["database"],
        category="decision",
    )
    service.save(raw2, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context", "--query", "authentication JWT"])

    assert result.exit_code == 0
    assert "Auth Token Setup" in result.output


def test_context_with_source_filter(env_home):
    """Test that memory context --source filters by agent source."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(title="CLI Memory", what="From CLI", source="claude-code")
    service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(title="Codex Memory", what="From Codex", source="codex")
    service.save(raw2, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context", "--source", "claude-code"])

    assert result.exit_code == 0
    assert "CLI Memory" in result.output
    assert "Codex Memory" not in result.output


def test_context_agents_md_format(env_home):
    """Test that memory context --format agents-md includes markdown header."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(title="Test Memory", what="Testing format")
    service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context", "--format", "agents-md"])

    assert result.exit_code == 0
    assert "## Memory Context" in result.output
    assert "Test Memory" in result.output
    assert "memory search" in result.output


def test_context_with_limit(env_home):
    """Test that memory context respects --limit option."""
    service = MemoryService(memory_home=str(env_home))
    for i in range(5):
        raw = RawMemoryInput(title=f"Memory {i}", what=f"Content {i}")
        service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context", "--limit", "2"])

    assert result.exit_code == 0
    assert "5 total, showing 2" in result.output
    # Count pointer lines (start with "- [")
    pointer_lines = [l for l in result.output.split("\n") if l.startswith("- [")]
    assert len(pointer_lines) == 2


def test_context_output_contains_pointer_fields(env_home):
    """Test that each pointer line contains date, title, category, and tags."""
    service = MemoryService(memory_home=str(env_home))
    raw = RawMemoryInput(
        title="Well Tagged Memory",
        what="Has all fields",
        category="pattern",
        tags=["python", "testing"],
    )
    service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["context"])

    assert result.exit_code == 0
    pointer_lines = [l for l in result.output.split("\n") if l.startswith("- [")]
    assert len(pointer_lines) == 1

    line = pointer_lines[0]
    assert "Well Tagged Memory" in line
    assert "[pattern]" in line
    assert "[python,testing]" in line


# --- reindex command tests ---


def test_reindex_no_memories(env_home):
    """Test that reindex handles empty vault gracefully."""
    runner = CliRunner()
    result = runner.invoke(main, ["reindex"])

    assert result.exit_code == 0
    assert "No memories to reindex." in result.output


def test_reindex_rebuilds_vectors(env_home):
    """Test that reindex command rebuilds vectors."""
    # Save some memories first
    service = MemoryService(memory_home=str(env_home))
    for i in range(3):
        raw = RawMemoryInput(title=f"Memory {i}", what=f"Content {i}")
        service.save(raw, project="test-project")
    service.close()

    runner = CliRunner()
    result = runner.invoke(main, ["reindex"])

    assert result.exit_code == 0
    assert "Re-indexed 3 memories" in result.output
    assert "768 dims" in result.output


def test_cli_help_shows_reindex(env_home):
    """Test that --help shows the reindex command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "reindex" in result.output


# --- setup command tests ---


def test_setup_help_shows_agents(env_home):
    """Test that memory setup --help lists agent subcommands."""
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "--help"])

    assert result.exit_code == 0
    assert "claude-code" in result.output
    assert "cursor" in result.output
    assert "codex" in result.output


def test_setup_claude_code_creates_hooks(env_home, tmp_path):
    """Test that memory setup claude-code installs hooks."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "claude-code", "--config-dir", str(claude_dir)])

    assert result.exit_code == 0
    assert "Installed" in result.output or "already" in result.output.lower()


def test_setup_cursor_creates_hooks(env_home, tmp_path):
    """Test that memory setup cursor installs hooks."""
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "cursor", "--config-dir", str(cursor_dir)])

    assert result.exit_code == 0


def test_setup_codex_creates_agents_md(env_home, tmp_path):
    """Test that memory setup codex writes AGENTS.md."""
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "codex", "--config-dir", str(codex_dir)])

    assert result.exit_code == 0
    assert (codex_dir / "AGENTS.md").exists()


# --- uninstall command tests ---


def test_uninstall_claude_code(env_home, tmp_path):
    """Test that memory uninstall claude-code removes hooks."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    runner = CliRunner()
    runner.invoke(main, ["setup", "claude-code", "--config-dir", str(claude_dir)])
    result = runner.invoke(main, ["uninstall", "claude-code", "--config-dir", str(claude_dir)])

    assert result.exit_code == 0
    assert "Removed" in result.output or "No" in result.output


# --- --project flag tests ---


def test_setup_claude_code_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project installs into .claude in cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "claude-code", "--project"])

    assert result.exit_code == 0
    mcp_path = tmp_path / ".mcp.json"
    assert mcp_path.exists()


def test_setup_cursor_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project installs into .cursor in cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "cursor", "--project"])

    assert result.exit_code == 0
    mcp_path = tmp_path / ".cursor" / "mcp.json"
    assert mcp_path.exists()


def test_setup_codex_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project installs into .codex in cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "codex", "--project"])

    assert result.exit_code == 0
    agents_path = tmp_path / ".codex" / "AGENTS.md"
    assert agents_path.exists()


def test_uninstall_claude_code_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project uninstalls from .claude in cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(main, ["setup", "claude-code", "--project"])
    result = runner.invoke(main, ["uninstall", "claude-code", "--project"])

    assert result.exit_code == 0
    assert "Removed" in result.output


def test_setup_opencode_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project installs opencode.json in cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "opencode", "--project"])

    assert result.exit_code == 0
    opencode_path = tmp_path / "opencode.json"
    assert opencode_path.exists()
    import json
    data = json.loads(opencode_path.read_text())
    assert "echovault" in data["mcp"]
    assert data["mcp"]["echovault"]["type"] == "local"
    assert data["mcp"]["echovault"]["command"] == ["memory", "mcp"]


def test_uninstall_opencode_project_flag(env_home, tmp_path, monkeypatch):
    """Test that --project uninstalls opencode.json from cwd."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    runner.invoke(main, ["setup", "opencode", "--project"])
    result = runner.invoke(main, ["uninstall", "opencode", "--project"])

    assert result.exit_code == 0
    assert "Removed" in result.output


def test_setup_codex_project_creates_config_toml(env_home, tmp_path, monkeypatch):
    """Test that --project installs both AGENTS.md and config.toml."""
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "codex", "--project"])

    assert result.exit_code == 0
    codex_dir = tmp_path / ".codex"
    assert (codex_dir / "AGENTS.md").exists()
    assert (codex_dir / "config.toml").exists()


def test_setup_help_shows_opencode(env_home):
    """Test that memory setup --help lists opencode subcommand."""
    runner = CliRunner()
    result = runner.invoke(main, ["setup", "--help"])

    assert result.exit_code == 0
    assert "opencode" in result.output


def test_mcp_command_exists():
    """Test that the mcp command is registered."""
    from click.testing import CliRunner
    from memory.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "mcp" in result.output.lower() or "stdio" in result.output.lower()
