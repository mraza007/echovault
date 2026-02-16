"""Tests for MCP server tools."""

import json
import os
from unittest.mock import patch

import pytest

from memory.core import MemoryService
from memory.models import RawMemoryInput


@pytest.fixture
def service(env_home):
    """Create a MemoryService for testing."""
    svc = MemoryService(memory_home=str(env_home))
    yield svc
    svc.close()


@pytest.fixture
def seeded_service(service):
    """Service with some memories already saved."""
    memories = [
        RawMemoryInput(
            title="Fixed auth session expiry",
            what="refreshSession defaulted to 60min",
            why="Stytch default param",
            tags=["auth", "session"],
            category="bug",
        ),
        RawMemoryInput(
            title="Chose JWT over session cookies",
            what="Switched to stateless JWT auth",
            why="Needed stateless auth for mobile API",
            impact="All endpoints require Bearer token",
            tags=["auth", "jwt", "architecture"],
            category="decision",
        ),
        RawMemoryInput(
            title="Docker compose for local dev",
            what="One-command local setup with minio and mailpit",
            tags=["docker", "devx"],
            category="context",
        ),
    ]
    for raw in memories:
        service.save(raw, project="test-project")
    return service


class TestMemorySaveTool:
    def test_save_creates_memory(self, service):
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            service,
            title="Test save via MCP",
            what="Testing the save tool",
            project="test-project",
        )
        data = json.loads(result)
        assert data["action"] == "created"
        assert "id" in data

    def test_save_with_all_fields(self, service):
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            service,
            title="Full memory",
            what="Complete memory with all fields",
            why="Testing completeness",
            impact="Verifies all fields stored",
            tags=["test", "complete"],
            category="learning",
            related_files=["src/test.py"],
            details="Extended details here",
            project="test-project",
        )
        data = json.loads(result)
        assert data["action"] == "created"

    def test_save_dedup_returns_updated(self, seeded_service):
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Fixed auth session expiry",
            what="Now passes 7-day duration explicitly",
            tags=["auth", "session", "stytch"],
            category="bug",
            project="test-project",
        )
        data = json.loads(result)
        assert data["action"] == "updated"


class TestMemorySearchTool:
    def test_search_returns_results(self, seeded_service):
        from memory.mcp_server import handle_memory_search

        result = handle_memory_search(
            seeded_service,
            query="authentication",
        )
        data = json.loads(result)
        assert len(data) > 0
        assert "title" in data[0]
        assert "score" in data[0]

    def test_search_with_project_filter(self, seeded_service):
        from memory.mcp_server import handle_memory_search

        result = handle_memory_search(
            seeded_service,
            query="auth",
            project="test-project",
        )
        data = json.loads(result)
        assert len(data) > 0
        for r in data:
            assert r["project"] == "test-project"

    def test_search_no_match_low_scores(self, seeded_service):
        from memory.mcp_server import handle_memory_search

        result = handle_memory_search(
            seeded_service,
            query="zzz_nonexistent_zzz",
        )
        data = json.loads(result)
        # Vector search may return results even for nonsense queries,
        # but FTS scores should be very low
        for r in data:
            assert r["score"] < 1.0


class TestMemoryContextTool:
    def test_context_returns_recent_memories(self, seeded_service):
        from memory.mcp_server import handle_memory_context

        result = handle_memory_context(
            seeded_service,
            project="test-project",
        )
        data = json.loads(result)
        assert data["total"] == 3
        assert len(data["memories"]) == 3

    def test_context_respects_limit(self, seeded_service):
        from memory.mcp_server import handle_memory_context

        result = handle_memory_context(
            seeded_service,
            project="test-project",
            limit=1,
        )
        data = json.loads(result)
        assert len(data["memories"]) == 1

    def test_context_empty_project(self, service):
        from memory.mcp_server import handle_memory_context

        result = handle_memory_context(
            service,
            project="empty-project",
        )
        data = json.loads(result)
        assert data["total"] == 0
        assert len(data["memories"]) == 0
