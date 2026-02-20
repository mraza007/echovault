"""Tests for core MemoryService."""

import os
from datetime import date
from unittest.mock import patch

import pytest

from memory.core import MemoryService
from memory.models import RawMemoryInput


def test_save_creates_markdown_file(env_home):
    """Test that save creates a markdown file in the vault."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Test Memory",
        what="Testing the save function",
        why="To verify markdown file creation",
        tags=["test"],
        category="decision"
    )

    result = service.save(raw, project="test-project")

    # Verify file was created
    assert os.path.exists(result["file_path"])

    # Verify file is in correct location
    today = date.today().isoformat()
    expected_path = os.path.join(
        str(env_home), "vault", "test-project", f"{today}-session.md"
    )
    assert result["file_path"] == expected_path

    # Verify file contains expected content
    with open(result["file_path"]) as f:
        content = f.read()

    assert "Test Memory" in content
    assert "Testing the save function" in content
    assert "To verify markdown file creation" in content

    service.close()


def test_save_indexes_memory_in_db(env_home):
    """Test that save indexes memory in DB (retrievable via get_memory)."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Indexed Memory",
        what="This should be searchable",
        tags=["db", "index"]
    )

    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    # Retrieve from database
    mem = service.db.get_memory(memory_id)

    assert mem is not None
    assert mem["title"] == "Indexed Memory"
    assert mem["what"] == "This should be searchable"
    assert mem["project"] == "test-project"

    service.close()


def test_save_with_details_stores_details(env_home):
    """Test that save with details stores details (retrievable via get_details)."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Memory with Details",
        what="Short summary",
        details="Long detailed explanation with code examples and context"
    )

    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    # Retrieve details
    details = service.get_details(memory_id)

    assert details is not None
    assert details.memory_id == memory_id
    assert details.body == "Long detailed explanation with code examples and context"

    service.close()


def test_save_warns_when_decision_has_no_details(env_home):
    """Test that decision memories without details return guidance warnings."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Decision without details",
        what="Switched auth strategy",
        category="decision",
    )

    result = service.save(raw, project="test-project")

    warnings = result.get("warnings", [])
    assert len(warnings) >= 1
    assert "should include details" in warnings[0]

    service.close()


def test_save_warns_when_details_are_too_short(env_home):
    """Test that short details trigger a warning."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Short details memory",
        what="Made an update",
        details="Too short",
        category="context",
    )

    result = service.save(raw, project="test-project")

    warnings = result.get("warnings", [])
    assert any("Details are brief" in w for w in warnings)

    service.close()


def test_save_warns_when_details_missing_sections(env_home):
    """Test that unstructured details warn about missing recommended sections."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Unstructured details memory",
        what="Updated deployment flow",
        details=(
            "This was a major update to deployment and rollback behavior. "
            "It changed defaults and required updates to scripts and docs."
        ),
        category="context",
    )

    result = service.save(raw, project="test-project")

    warnings = result.get("warnings", [])
    assert any("missing recommended sections" in w for w in warnings)

    service.close()


def test_save_no_warnings_for_structured_details(env_home):
    """Test that structured and sufficiently long details avoid warnings."""
    service = MemoryService(memory_home=str(env_home))

    structured_details = """Context:
Authentication setup had drifted between API and mobile clients, causing token mismatches and inconsistent refresh handling across environments.

Options considered:
- Keep mixed session+token flow and patch edge cases.
- Move everything to JWT with consistent issuer/audience and refresh semantics.

Decision:
Standardized on JWT for all clients with explicit refresh token rotation rules and environment-specific validation settings.

Tradeoffs:
Requires migration work and temporary compatibility shims, but removes repeated session bugs and simplifies API contracts.

Follow-up:
Add migration notes, monitor auth failures for one week, and remove compatibility code after rollout.
"""
    raw = RawMemoryInput(
        title="Structured details memory",
        what="Standardized authentication flow",
        details=structured_details,
        category="decision",
    )

    result = service.save(raw, project="test-project")

    warnings = result.get("warnings", [])
    assert warnings == []

    service.close()


def test_save_redacts_secrets(env_home):
    """Test that save redacts secrets (sk_live_ in what field is replaced)."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Memory with Secret",
        what="Using API key sk_live_abc123xyz for payment processing"
    )

    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    # Verify secret was redacted in database
    mem = service.db.get_memory(memory_id)
    assert mem is not None
    assert "sk_live_abc123xyz" not in mem["what"]
    assert "[REDACTED]" in mem["what"]

    # Verify secret was redacted in markdown file
    with open(result["file_path"]) as f:
        content = f.read()

    assert "sk_live_abc123xyz" not in content
    assert "[REDACTED]" in content

    service.close()


def test_save_redacts_explicit_tags_in_details(env_home):
    """Test that save redacts explicit <redacted> tags in details."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Memory with Redacted Tags",
        what="Configuration updated",
        details="Database config: <redacted>host=secret.db password=pass123</redacted> works now"
    )

    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    # Verify tags were redacted in details
    details = service.get_details(memory_id)
    assert details is not None
    assert "<redacted>" not in details.body
    assert "</redacted>" not in details.body
    assert "[REDACTED]" in details.body
    assert "host=secret.db password=pass123" not in details.body

    service.close()


def test_search_returns_results(env_home):
    """Test that search returns results."""
    service = MemoryService(memory_home=str(env_home))

    # Save some memories
    raw1 = RawMemoryInput(
        title="Python FastAPI Setup",
        what="Configured FastAPI application with async routes"
    )
    service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(
        title="Database Migration",
        what="Added new column to users table"
    )
    service.save(raw2, project="test-project")

    # Search for "FastAPI"
    results = service.search("FastAPI", limit=5)

    assert len(results) > 0
    # Should find the FastAPI memory
    titles = [r["title"] for r in results]
    assert "Python FastAPI Setup" in titles

    service.close()


def test_search_filter_by_project(env_home):
    """Test that search filter by project works."""
    service = MemoryService(memory_home=str(env_home))

    # Save memories to different projects
    raw1 = RawMemoryInput(
        title="Project A Memory",
        what="Something in project A"
    )
    service.save(raw1, project="project-a")

    raw2 = RawMemoryInput(
        title="Project B Memory",
        what="Something in project B"
    )
    service.save(raw2, project="project-b")

    # Search filtered to project A
    results = service.search("Something", limit=5, project="project-a")

    assert len(results) > 0
    # All results should be from project A
    for r in results:
        assert r["project"] == "project-a"

    # Verify project B memory is not in results
    titles = [r["title"] for r in results]
    assert "Project B Memory" not in titles

    service.close()


def test_get_details_returns_none_when_no_details(env_home):
    """Test that get_details returns None when no details exist."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Memory without Details",
        what="No details provided"
    )

    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    # Try to get details
    details = service.get_details(memory_id)

    assert details is None

    service.close()


def test_delete_removes_memory(env_home):
    """Test that delete removes a memory via the service."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(
        title="Memory to Delete",
        what="This will be deleted",
        details="Detailed info that should also be removed",
    )
    result = service.save(raw, project="test-project")
    memory_id = result["id"]

    deleted = service.delete(memory_id)
    assert deleted is True

    # Should not appear in search
    results = service.search("Memory to Delete", limit=5)
    assert all(r["id"] != memory_id for r in results)

    # Details should be gone
    assert service.get_details(memory_id) is None

    service.close()


def test_delete_returns_false_for_nonexistent(env_home):
    """Test that delete returns False for unknown IDs."""
    service = MemoryService(memory_home=str(env_home))

    deleted = service.delete("nonexistent-id-123")
    assert deleted is False

    service.close()


def test_save_stores_embedding_dimension(env_home):
    """Test that first save detects and stores embedding dimension."""
    service = MemoryService(memory_home=str(env_home))

    raw = RawMemoryInput(title="First Memory", what="Triggers dimension detection")
    service.save(raw, project="test-project")

    # Dimension should be stored in meta
    dim = service.db.get_embedding_dim()
    assert dim == 768  # FakeEmbeddingProvider uses 768

    service.close()


def test_save_creates_vec_table_on_first_use(env_home):
    """Test that the vector table is created on first save."""
    service = MemoryService(memory_home=str(env_home))

    # Before save, no vec table
    assert not service.db.has_vec_table()

    raw = RawMemoryInput(title="First Memory", what="Creates vec table")
    service.save(raw, project="test-project")

    # After save, vec table exists
    assert service.db.has_vec_table()

    service.close()


def test_search_fts_only_without_vectors(env_home):
    """Test that search works with FTS only when vectors are unavailable."""
    service = MemoryService(memory_home=str(env_home))

    # Force vectors unavailable
    service._vectors_available = False

    raw = RawMemoryInput(title="FTS Memory", what="Searchable via keyword")
    service.save(raw, project="test-project")

    # Search should still return results via FTS
    results = service.search("keyword", limit=5)
    assert len(results) >= 1
    assert results[0]["title"] == "FTS Memory"

    service.close()


def test_reindex_rebuilds_vectors(env_home):
    """Test that reindex rebuilds the vector table."""
    service = MemoryService(memory_home=str(env_home))

    # Save some memories
    for i in range(3):
        raw = RawMemoryInput(title=f"Memory {i}", what=f"Content {i}")
        service.save(raw, project="test-project")

    # Reindex
    result = service.reindex()

    assert result["count"] == 3
    assert result["dim"] == 768

    # Vectors should be available
    assert service.vectors_available

    service.close()


def test_save_dedup_updates_existing_memory(env_home):
    """Test that saving a similar memory updates the existing one."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(
        title="Fixed auth session expiry",
        what="Session defaulted to 60min instead of 7 days",
        why="Stytch default param",
        tags=["auth", "session"],
        category="bug",
    )
    result1 = service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(
        title="Fixed auth session expiry",
        what="Both refresh calls now pass 7-day duration",
        why="Stytch refreshSession had wrong default",
        impact="Users no longer logged out prematurely",
        tags=["auth", "stytch"],
        category="bug",
    )
    result2 = service.save(raw2, project="test-project")

    assert result2["action"] == "updated"
    assert result2["id"] == result1["id"]

    mem = service.db.get_memory(result1["id"])
    assert mem["what"] == "Both refresh calls now pass 7-day duration"
    assert mem["updated_count"] == 1

    service.close()


def test_save_dedup_does_not_match_different_project(env_home):
    """Test that dedup only matches within the same project."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(
        title="Database migration",
        what="Added users table",
        category="decision",
    )
    service.save(raw1, project="project-a")

    raw2 = RawMemoryInput(
        title="Database migration",
        what="Added users table",
        category="decision",
    )
    result2 = service.save(raw2, project="project-b")

    assert result2["action"] == "created"
    service.close()


def test_save_dedup_creates_new_when_no_match(env_home):
    """Test that dissimilar memories create new entries."""
    service = MemoryService(memory_home=str(env_home))

    raw1 = RawMemoryInput(
        title="Auth session fix",
        what="Fixed session timeout",
        category="bug",
    )
    service.save(raw1, project="test-project")

    raw2 = RawMemoryInput(
        title="Database schema redesign",
        what="Normalized the orders table",
        category="decision",
    )
    result2 = service.save(raw2, project="test-project")

    assert result2["action"] == "created"
    service.close()


def test_dimension_mismatch_falls_back_to_fts(env_home):
    """Test that dimension mismatch triggers FTS-only fallback."""
    from tests.conftest import FakeEmbeddingProvider

    service = MemoryService(memory_home=str(env_home))

    # Save with 768-dim provider
    raw = RawMemoryInput(title="Original Memory", what="With 768 dims")
    service.save(raw, project="test-project")

    assert service.db.get_embedding_dim() == 768

    # Switch to a different dimension provider
    service._embedding_provider = FakeEmbeddingProvider(dim=384)
    service._vectors_available = None  # Reset cache

    # Search should still work via FTS fallback
    results = service.search("Original", limit=5)
    assert len(results) >= 1

    service.close()
