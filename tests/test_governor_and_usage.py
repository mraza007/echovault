"""Tests for Memory Governor, Collective Wisdom, and usage tracking."""

import json
from datetime import datetime, timezone

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


class TestUsageTracking:
    """Tests for memory access tracking in database."""

    def test_record_access_increments_counters(self, seeded_service):
        """Test that record_access increments access_count and session_access_count."""
        from memory.mcp_server import handle_memory_save

        # Save a memory first
        result = handle_memory_save(
            seeded_service,
            title="Test memory for access tracking",
            what="Testing access tracking functionality",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # Initial access
        seeded_service.db.record_access(memory_id, "session-1")
        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 1
        assert mem["session_access_count"] == 1
        assert mem["last_session_id"] == "session-1"

    def test_record_access_same_session_increments_both(self, seeded_service):
        """Test that same session increments both counters."""
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Test memory same session",
            what="Testing same session access tracking",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # First access
        seeded_service.db.record_access(memory_id, "session-1")
        # Second access in same session
        seeded_service.db.record_access(memory_id, "session-1")
        # Third access in same session
        seeded_service.db.record_access(memory_id, "session-1")

        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 3
        assert mem["session_access_count"] == 3

    def test_record_access_new_session_resets_session_count(self, seeded_service):
        """Test that new session resets session_access_count but keeps total."""
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Test memory new session",
            what="Testing new session access tracking",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # Access in first session
        seeded_service.db.record_access(memory_id, "session-1")
        seeded_service.db.record_access(memory_id, "session-1")

        # Access in new session
        seeded_service.db.record_access(memory_id, "session-2")

        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 3  # Total keeps incrementing
        assert mem["session_access_count"] == 1  # Reset for new session
        assert mem["last_session_id"] == "session-2"

    def test_record_access_updates_timestamp(self, seeded_service):
        """Test that record_access updates last_accessed_at."""
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Test memory timestamp",
            what="Testing timestamp tracking",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        before = datetime.now(timezone.utc).isoformat()
        seeded_service.db.record_access(memory_id, "session-1")
        after = datetime.now(timezone.utc).isoformat()

        mem = seeded_service.db.get_memory(memory_id)
        assert mem["last_accessed_at"] is not None
        assert before <= mem["last_accessed_at"] <= after

    def test_get_details_records_usage_by_default(self, seeded_service):
        """Test that get_details records usage by default."""
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Test memory details usage",
            what="Testing get_details usage tracking",
            details="Some details here",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # get_details should record usage by default
        seeded_service.get_details(memory_id)

        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 1

    def test_get_details_no_record_usage_when_disabled(self, seeded_service):
        """Test that get_details doesn't record usage when record_usage=False."""
        from memory.mcp_server import handle_memory_save

        result = handle_memory_save(
            seeded_service,
            title="Test memory no usage tracking",
            what="Testing get_details without usage tracking",
            details="Some details here",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # get_details should NOT record usage when explicitly disabled
        seeded_service.get_details(memory_id, record_usage=False)

        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 0


class TestCoreMemoryUsage:
    """Tests for Core Memory usage tracking."""

    def test_record_core_memory_usage_creates_entry(self, service):
        """Test that record_core_memory_usage creates core_memory_usage entry."""
        core_id = "core-memory-123"
        service.db.record_core_memory_usage(core_id, "session-1")

        cursor = service.db.conn.cursor()
        cursor.execute("SELECT * FROM core_memory_usage WHERE id = ?", (core_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row["id"] == core_id
        assert row["unused_sessions_count"] == 0
        assert row["last_used_session_id"] == "session-1"
        assert row["last_used_at"] is not None

    def test_record_core_memory_usage_updates_existing(self, service):
        """Test that record_core_memory_usage updates existing entry."""
        core_id = "core-memory-456"

        # First usage
        service.db.record_core_memory_usage(core_id, "session-1")

        # Increment unused sessions to simulate time passing
        service.db.increment_unused_sessions_for_core("session-2")

        # Second usage
        service.db.record_core_memory_usage(core_id, "session-2")

        cursor = service.db.conn.cursor()
        cursor.execute("SELECT * FROM core_memory_usage WHERE id = ?", (core_id,))
        row = cursor.fetchone()

        assert row["unused_sessions_count"] == 0  # Reset
        assert row["last_used_session_id"] == "session-2"

    def test_increment_unused_sessions_for_core(self, service):
        """Test that increment_unused_sessions_for_core increments for unused entries."""
        core_id = "core-memory-789"
        service.db.record_core_memory_usage(core_id, "session-1")

        # Simulate new session without using this core memory
        service.db.increment_unused_sessions_for_core("session-2")

        cursor = service.db.conn.cursor()
        cursor.execute("SELECT * FROM core_memory_usage WHERE id = ?", (core_id,))
        row = cursor.fetchone()

        assert row["unused_sessions_count"] == 1


class TestMCPUsageTracking:
    """Tests for MCP memory_record_usage tool."""

    def test_record_usage_core(self, service):
        """Test memory_record_usage for core memory."""
        from memory.mcp_server import handle_memory_record_usage

        result = handle_memory_record_usage(
            service,
            usage_type="core",
            memory_id="core-test-123",
        )
        data = json.loads(result)

        assert data["status"] == "success"
        assert "core-test-123" in data["message"]

    def test_record_usage_main(self, seeded_service):
        """Test memory_record_usage for main memory."""
        from memory.mcp_server import handle_memory_save, handle_memory_record_usage

        # Save a memory
        result = handle_memory_save(
            seeded_service,
            title="Test main memory usage",
            what="Testing main memory usage tracking via MCP",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # Record usage
        result = handle_memory_record_usage(
            seeded_service,
            usage_type="main",
            memory_id=memory_id,
        )
        data = json.loads(result)

        assert data["status"] == "success"
        assert memory_id in data["message"]

        # Verify access was recorded
        mem = seeded_service.db.get_memory(memory_id)
        assert mem["access_count"] == 1

    def test_record_usage_invalid_type(self, service):
        """Test memory_record_usage with invalid type."""
        from memory.mcp_server import handle_memory_record_usage

        result = handle_memory_record_usage(
            service,
            usage_type="invalid",
            memory_id="test-123",
        )
        data = json.loads(result)

        assert data["status"] == "error"
        assert "Invalid usage type" in data["message"]


class TestMemoryGovernor:
    """Tests for Memory Governor MCP tool."""

    def test_governor_returns_actions_list(self, service):
        """Test that governor returns actions list."""
        from memory.mcp_server import handle_memory_governor

        result = handle_memory_governor(service)
        data = json.loads(result)

        assert "actions" in data
        assert isinstance(data["actions"], list)
        assert "next_session_id" in data
        assert "message" in data

    def test_governor_promotes_highly_accessed_memories(self, seeded_service):
        """Test that governor promotes memories accessed 3+ times in session."""
        from memory.mcp_server import handle_memory_save, handle_memory_governor

        # Save a memory
        result = handle_memory_save(
            seeded_service,
            title="Hot memory for promotion",
            what="This memory will be accessed many times",
            project="test-project",
        )
        data = json.loads(result)
        memory_id = data["id"]

        # Access 3 times in same session
        for _ in range(3):
            seeded_service.db.record_access(memory_id, seeded_service.session_id)

        # Run governor
        result = handle_memory_governor(seeded_service)
        data = json.loads(result)

        # Should recommend promotion
        promotion_actions = [a for a in data["actions"] if a["action"] == "ADD"]
        assert len(promotion_actions) > 0

        # Find our memory in actions
        our_memory_action = [a for a in promotion_actions if a.get("id") == memory_id]
        assert len(our_memory_action) == 1
        assert "Used 3 times" in our_memory_action[0]["reason"]

    def test_governor_demotes_unused_core_memories(self, service):
        """Test that governor demotes core memories unused for 10+ sessions."""
        from memory.mcp_server import handle_memory_governor

        # Simulate an old core memory
        core_id = "old-core-memory"
        service.db.record_core_memory_usage(core_id, "old-session")

        # Simulate 10 new sessions without using it
        for i in range(10):
            service.db.increment_unused_sessions_for_core(f"session-{i}")

        # Run governor
        result = handle_memory_governor(service)
        data = json.loads(result)

        # Should recommend demotion
        demotion_actions = [a for a in data["actions"] if a["action"] == "DELETE"]
        assert len(demotion_actions) > 0

        our_memory_action = [a for a in demotion_actions if a.get("id") == core_id]
        assert len(our_memory_action) == 1
        assert "Unused for" in our_memory_action[0]["reason"]

    def test_governor_generates_new_session_id(self, service):
        """Test that governor generates new session ID."""
        from memory.mcp_server import handle_memory_governor

        old_session_id = service.session_id

        result = handle_memory_governor(service)
        data = json.loads(result)

        new_session_id = data["next_session_id"]
        assert new_session_id != old_session_id
        assert len(new_session_id) == 36  # UUID length


class TestCollectiveWisdom:
    """Tests for Collective Wisdom MCP tool."""

    def test_collective_solve_returns_response(self, seeded_service):
        """Test that collective_solve returns structured response."""
        from memory.mcp_server import handle_memory_collective_solve

        result = handle_memory_collective_solve(
            seeded_service,
            task_description="How do I refactor this complex code?",
        )
        data = json.loads(result)

        assert "status" in data
        assert data["status"] == "collective_sync"
        assert "relevant_knowledge_domains" in data
        assert "strategic_suggestions" in data
        assert "message" in data

    def test_collective_solve_network_keywords(self, seeded_service):
        """Test that collective_solve suggests network tools for network tasks."""
        from memory.mcp_server import handle_memory_collective_solve

        result = handle_memory_collective_solve(
            seeded_service,
            task_description="Debug SSH connection issues to server",
        )
        data = json.loads(result)

        suggestions = data["strategic_suggestions"]
        assert any("tcpdump" in s for s in suggestions)
        assert any("SSH" in s or "ssh" in s for s in suggestions)

    def test_collective_solve_refactor_keywords(self, seeded_service):
        """Test that collective_solve suggests ultracode for refactoring tasks."""
        from memory.mcp_server import handle_memory_collective_solve

        result = handle_memory_collective_solve(
            seeded_service,
            task_description="Refactor complex dependencies in class hierarchy",
        )
        data = json.loads(result)

        suggestions = data["strategic_suggestions"]
        assert any("ultracode" in s for s in suggestions)
        assert any("refactor" in s.lower() for s in suggestions)

    def test_collective_solve_docker_keywords(self, seeded_service):
        """Test that collective_solve suggests docker tools for container tasks."""
        from memory.mcp_server import handle_memory_collective_solve

        result = handle_memory_collective_solve(
            seeded_service,
            task_description="Build docker container with specific SDK requirements",
        )
        data = json.loads(result)

        suggestions = data["strategic_suggestions"]
        assert any("docker" in s.lower() for s in suggestions)

    def test_collective_solve_includes_top_memories(self, seeded_service):
        """Test that collective_solve includes top relevant memories."""
        from memory.mcp_server import handle_memory_collective_solve

        result = handle_memory_collective_solve(
            seeded_service,
            task_description="authentication JWT tokens",
        )
        data = json.loads(result)

        assert "top_memories" in data
        assert isinstance(data["top_memories"], list)
        # Should find the JWT memory we seeded
        assert any("JWT" in m.get("title", "") for m in data["top_memories"])


class TestDatabaseMigrations:
    """Tests for database schema migrations."""

    def test_memories_table_has_usage_columns(self, service):
        """Test that memories table has all usage tracking columns."""
        cursor = service.db.conn.cursor()
        cursor.execute("PRAGMA table_info(memories)")
        columns = {row["name"] for row in cursor.fetchall()}

        assert "access_count" in columns
        assert "session_access_count" in columns
        assert "last_session_id" in columns
        assert "last_accessed_at" in columns
        # Also verify archive columns from upstream
        assert "status" in columns
        assert "archived_at" in columns
        assert "archive_reason" in columns
        assert "superseded_by" in columns

    def test_core_memory_usage_table_exists(self, service):
        """Test that core_memory_usage table exists."""
        cursor = service.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_memory_usage'")
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "core_memory_usage"

    def test_core_memory_usage_table_schema(self, service):
        """Test that core_memory_usage table has correct schema."""
        cursor = service.db.conn.cursor()
        cursor.execute("PRAGMA table_info(core_memory_usage)")
        columns = {row["name"]: row for row in cursor.fetchall()}

        assert "id" in columns
        assert "unused_sessions_count" in columns
        assert "last_used_session_id" in columns
        assert "last_used_at" in columns

        # id should be primary key
        assert columns["id"]["pk"] == 1
