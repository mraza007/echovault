"""Tests for dashboard service flows and Textual app boot."""

import json
from pathlib import Path

import pytest

from memory.core import MemoryService
from memory.dashboard import MemoryDashboardApp
from memory.dashboard.widgets.memory_table import VimDataTable
from memory.markdown import parse_session_file
from memory.models import RawMemoryInput


@pytest.fixture
def dashboard_service(env_home):
    service = MemoryService(memory_home=str(env_home))
    memories = [
        RawMemoryInput(
            title="Auth timeout fix",
            what="Fixed the auth timeout regression",
            why="Sessions expired too early",
            impact="Stability improved",
            tags=["auth", "bug"],
            category="bug",
            details="Original bug details",
            source="codex",
        ),
        RawMemoryInput(
            title="Auth timeout follow-up",
            what="Added telemetry around auth timeouts",
            tags=["auth", "telemetry"],
            category="context",
            details="Telemetry details",
            source="codex",
        ),
        RawMemoryInput(
            title="Dependency policy",
            what="Pinned UI dependencies monthly",
            tags=["deps"],
            category="decision",
            source="codex",
        ),
    ]
    for raw in memories:
        service.save(raw, project="dashboard-project")
    yield service
    service.close()


def test_update_archive_restore_and_merge_roundtrip(dashboard_service):
    records = dashboard_service.list_memories(project="dashboard-project")
    auth_fix = next(record for record in records if record["title"] == "Auth timeout fix")
    follow_up = next(record for record in records if record["title"] == "Auth timeout follow-up")

    dashboard_service.update_memory_record(
        auth_fix["id"],
        title="Auth timeout regression",
        what="Fixed the auth timeout regression thoroughly",
        why="Sessions expired too early",
        impact="Stability improved",
        category="bug",
        tags=["auth", "bug", "dashboard"],
        source="dashboard",
        details="Updated dashboard details",
    )

    updated = dashboard_service.get_memory_record(auth_fix["id"])
    assert updated is not None
    assert updated["title"] == "Auth timeout regression"
    assert "Updated dashboard details" in updated["details"]

    session_path = Path(updated["file_path"])
    content = session_path.read_text(encoding="utf-8")
    assert "<!-- memory-id:" in content
    assert "### Auth timeout regression" in content

    dashboard_service.archive_memory(follow_up["id"], reason="dashboard-test", superseded_by=auth_fix["id"])
    active_ids = {record["id"] for record in dashboard_service.list_memories(project="dashboard-project")}
    assert follow_up["id"] not in active_ids

    archived = dashboard_service.get_memory_record(follow_up["id"])
    assert archived is not None
    assert archived["status"] == "archived"
    document = parse_session_file(archived["file_path"])
    assert any(entry.id == follow_up["id"] and entry.status == "archived" for entry in document.entries)

    dashboard_service.restore_memory(follow_up["id"])
    restored = dashboard_service.get_memory_record(follow_up["id"])
    assert restored is not None
    assert restored["status"] == "active"

    dashboard_service.merge_memories(auth_fix["id"], [follow_up["id"]])
    merged = dashboard_service.get_memory_record(auth_fix["id"])
    archived_follow_up = dashboard_service.get_memory_record(follow_up["id"])

    assert merged is not None
    assert archived_follow_up is not None
    assert "Merged from:" in merged["details"]
    merged_tags = json.loads(merged["tags"]) if isinstance(merged["tags"], str) else merged["tags"]
    assert "telemetry" in merged_tags
    assert archived_follow_up["status"] == "archived"
    assert archived_follow_up["superseded_by"] == auth_fix["id"]


def test_duplicate_candidates_prioritize_same_project_matches(dashboard_service):
    dashboard_service.save(
        RawMemoryInput(
            title="Dependency policy update",
            what="Pinned UI dependencies each month",
            category="decision",
            tags=["deps", "ui"],
        ),
        project="dashboard-project",
    )

    candidates = dashboard_service.find_duplicate_candidates(project="dashboard-project")
    assert candidates
    top = candidates[0]
    assert top["project"] == "dashboard-project"
    assert {"Dependency policy", "Dependency policy update"} == {top["left_title"], top["right_title"]}


@pytest.mark.anyio
async def test_dashboard_app_boots_and_filters(dashboard_service):
    app = MemoryDashboardApp(service=dashboard_service, initial_project="dashboard-project")
    async with app.run_test() as pilot:
        await pilot.pause()

        # Switch to memories view
        await pilot.press("2")
        await pilot.pause()

        # Search for a specific memory
        from textual.widgets import Input

        app.query_one("#mem-search", Input).value = "Dependency"
        app.refresh_memories()
        await pilot.pause()

        table = app.query_one("#mem-table", VimDataTable)
        assert table.row_count == 1
