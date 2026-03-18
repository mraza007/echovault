"""Tests for SQLite database layer with FTS5 and sqlite-vec."""

import json
import struct
import tempfile
from pathlib import Path

import pytest

from memory.db import DimensionMismatchError, MemoryDB, _build_fts_query
from memory.models import Memory, MemoryDetail, RawMemoryInput


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        memory_db = MemoryDB(str(db_path))
        yield memory_db
        memory_db.close()


@pytest.fixture
def sample_memory():
    """Create a sample memory for testing."""
    raw = RawMemoryInput(
        title="Test Authentication Bug",
        what="Fixed token validation in auth middleware",
        why="Users were getting logged out unexpectedly",
        impact="Improved session stability by 95%",
        tags=["auth", "security", "bug-fix"],
        category="bug",
        related_files=["src/auth/middleware.py", "tests/test_auth.py"],
        source="conversation-2024-01-15.md",
    )
    return Memory.from_raw(raw, project="my-project", file_path="memories/2024-01.md")


@pytest.fixture
def sample_detail(sample_memory):
    """Create sample memory detail."""
    return MemoryDetail(
        memory_id=sample_memory.id,
        body="Detailed analysis of the authentication bug...\n\nRoot cause was..."
    )


def test_db_creates_tables_without_error():
    """Test that database initializes and creates tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = MemoryDB(str(db_path))
        assert db is not None
        db.close()


def test_insert_and_retrieve_memory(db, sample_memory):
    """Test inserting and retrieving a memory."""
    rowid = db.insert_memory(sample_memory)
    assert rowid > 0

    result = db.get_memory(sample_memory.id)
    assert result is not None
    assert result["id"] == sample_memory.id
    assert result["title"] == sample_memory.title
    assert result["what"] == sample_memory.what
    assert result["why"] == sample_memory.why
    assert result["impact"] == sample_memory.impact
    assert result["category"] == sample_memory.category
    assert result["project"] == sample_memory.project
    assert result["source"] == sample_memory.source
    assert result["file_path"] == sample_memory.file_path
    assert result["section_anchor"] == sample_memory.section_anchor
    assert result["created_at"] == sample_memory.created_at
    assert result["updated_at"] == sample_memory.updated_at

    # Check JSON fields are deserialized
    assert json.loads(result["tags"]) == sample_memory.tags
    assert json.loads(result["related_files"]) == sample_memory.related_files


def test_insert_with_details_retrieve_details(db, sample_memory, sample_detail):
    """Test inserting memory with details and retrieving them."""
    rowid = db.insert_memory(sample_memory, details=sample_detail.body)
    assert rowid > 0

    detail = db.get_details(sample_memory.id)
    assert detail is not None
    assert detail.memory_id == sample_memory.id
    assert detail.body == sample_detail.body


def test_get_details_with_prefix(db, sample_memory, sample_detail):
    """Test that get_details works with a UUID prefix."""
    db.insert_memory(sample_memory, details=sample_detail.body)

    prefix = sample_memory.id[:8]
    detail = db.get_details(prefix)
    assert detail is not None
    assert detail.memory_id == sample_memory.id
    assert detail.body == sample_detail.body


def test_get_details_returns_none_when_no_details(db, sample_memory):
    """Test that get_details returns None when no details exist."""
    db.insert_memory(sample_memory)
    detail = db.get_details(sample_memory.id)
    assert detail is None


def test_fts_search_finds_matching_memories(db, sample_memory):
    """Test FTS search finds matching memories."""
    db.insert_memory(sample_memory)

    results = db.fts_search("authentication", limit=10)
    assert len(results) > 0
    assert results[0]["id"] == sample_memory.id
    assert results[0]["score"] > 0  # BM25 score should be positive


def test_fts_search_returns_empty_for_no_matches(db, sample_memory):
    """Test FTS search returns empty list when no matches."""
    db.insert_memory(sample_memory)

    results = db.fts_search("nonexistent", limit=10)
    assert len(results) == 0


def test_fts_prefix_matching(db):
    """Test FTS prefix matching works correctly."""
    raw = RawMemoryInput(
        title="Authentication System",
        what="Implemented OAuth2 authentication",
        tags=["auth"],
        category="decision",
    )
    memory = Memory.from_raw(raw, project="test-project", file_path="test.md")
    db.insert_memory(memory)

    # Search with prefix "auth" should find "authentication"
    results = db.fts_search("auth", limit=10)
    assert len(results) > 0
    assert results[0]["id"] == memory.id


def test_build_fts_query_filters_stopword_noise():
    """Common glue words should not dominate prefix FTS queries."""
    query = _build_fts_query("a musician in the mist")
    assert query == '"musician"* OR "mist"*'


def test_build_fts_query_falls_back_for_short_query():
    """Short queries should still remain searchable."""
    query = _build_fts_query("AI")
    assert query == '"ai"*'


def test_insert_and_search_vectors(db):
    """Test inserting and searching vectors."""
    # Set up vec table with correct dimension
    db.ensure_vec_table(384)

    # Create three memories with different embeddings
    memories = []
    embeddings = []

    for i, title in enumerate(["Database Schema", "API Design", "Database Queries"]):
        raw = RawMemoryInput(
            title=title,
            what=f"Content about {title.lower()}",
            category="pattern",
        )
        memory = Memory.from_raw(raw, project="test-project", file_path="test.md")
        rowid = db.insert_memory(memory)
        memories.append((memory, rowid))

        # Create simple embeddings (in reality, these would be from a model)
        # Make first and third similar (database-related)
        if i == 0:  # Database Schema
            embedding = [1.0] * 384
        elif i == 1:  # API Design
            embedding = [0.0] * 384
        else:  # Database Queries
            embedding = [0.9] * 384

        embeddings.append(embedding)
        db.insert_vector(rowid, embedding)

    # Search with query similar to "Database Schema"
    query_embedding = [0.95] * 384
    results = db.vector_search(query_embedding, limit=3)

    assert len(results) == 3
    # First two results should be database-related (similar embeddings)
    assert results[0]["title"] in ["Database Schema", "Database Queries"]
    assert results[1]["title"] in ["Database Schema", "Database Queries"]
    # Last result should be API Design (different embedding)
    assert results[2]["title"] == "API Design"

    # Check similarity scores (1 - distance)
    assert results[0]["score"] > results[2]["score"]


def test_vector_search_with_project_filter_overfetches_candidates(db):
    """Project filtering should still return in-scope vector hits when global top-k differs."""
    db.ensure_vec_table(3)

    raw_other = RawMemoryInput(title="Other project exact hit", what="Global nearest vector", category="context")
    other = Memory.from_raw(raw_other, project="other-project", file_path="test.md")
    other_rowid = db.insert_memory(other)
    db.insert_vector(other_rowid, [1.0, 0.0, 0.0])

    raw_target = RawMemoryInput(title="Target project near hit", what="Project-scoped vector", category="context")
    target = Memory.from_raw(raw_target, project="target-project", file_path="test.md")
    target_rowid = db.insert_memory(target)
    db.insert_vector(target_rowid, [0.9, 0.0, 0.0])

    results = db.vector_search([1.0, 0.0, 0.0], limit=1, project="target-project")

    assert len(results) == 1
    assert results[0]["id"] == target.id
    assert results[0]["project"] == "target-project"
    assert results[0]["score"] > 0


def test_filter_by_project(db):
    """Test filtering search results by project."""
    # Create memories in different projects
    for project in ["project-a", "project-b"]:
        for i in range(2):
            raw = RawMemoryInput(
                title=f"{project} Memory {i}",
                what=f"Content for {project}",
                category="context",
            )
            memory = Memory.from_raw(raw, project=project, file_path="test.md")
            db.insert_memory(memory)

    # Search in project-a only
    results = db.fts_search("Memory", limit=10, project="project-a")
    assert len(results) == 2
    assert all(r["project"] == "project-a" for r in results)

    # Search in project-b only
    results = db.fts_search("Memory", limit=10, project="project-b")
    assert len(results) == 2
    assert all(r["project"] == "project-b" for r in results)


def test_filter_by_source(db):
    """Test filtering search results by source."""
    # Create memories from different sources
    for source in ["conversation-1.md", "conversation-2.md"]:
        for i in range(2):
            raw = RawMemoryInput(
                title=f"Memory {i}",
                what=f"Content from {source}",
                source=source,
                category="learning",
            )
            memory = Memory.from_raw(raw, project="test-project", file_path="test.md")
            db.insert_memory(memory)

    # Search in conversation-1.md only
    results = db.fts_search("Memory", limit=10, source="conversation-1.md")
    assert len(results) == 2
    assert all(r["source"] == "conversation-1.md" for r in results)

    # Search in conversation-2.md only
    results = db.fts_search("Memory", limit=10, source="conversation-2.md")
    assert len(results) == 2
    assert all(r["source"] == "conversation-2.md" for r in results)


def test_has_details_flag(db, sample_memory):
    """Test has_details flag is set correctly."""
    # Insert without details
    db.insert_memory(sample_memory)
    result = db.get_memory(sample_memory.id)
    assert result["has_details"] == 0  # SQLite returns 0 for False

    # Insert another with details
    raw = RawMemoryInput(
        title="Memory with Details",
        what="This has details",
        category="context",
    )
    memory_with_details = Memory.from_raw(raw, project="test-project", file_path="test.md")
    db.insert_memory(memory_with_details, details="Detailed information here")

    result_with_details = db.get_memory(memory_with_details.id)
    assert result_with_details["has_details"] == 1  # SQLite returns 1 for True


def test_set_meta_get_meta(db):
    """Test setting and getting metadata."""
    db.set_meta("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
    value = db.get_meta("embedding_model")
    assert value == "sentence-transformers/all-MiniLM-L6-v2"

    # Test non-existent key
    value = db.get_meta("nonexistent")
    assert value is None


def test_ensure_vec_table_stores_dimension(db):
    """Test that ensure_vec_table stores dimension in meta."""
    db.ensure_vec_table(768)
    assert db.get_embedding_dim() == 768
    assert db.has_vec_table()


def test_ensure_vec_table_raises_on_mismatch(db):
    """Test that ensure_vec_table raises on dimension mismatch."""
    db.ensure_vec_table(768)

    with pytest.raises(DimensionMismatchError) as exc_info:
        db.ensure_vec_table(384)

    assert exc_info.value.stored_dim == 768
    assert exc_info.value.new_dim == 384
    assert "memory reindex" in str(exc_info.value)


def test_ensure_vec_table_idempotent_same_dim(db):
    """Test that ensure_vec_table is idempotent for same dimension."""
    db.ensure_vec_table(768)
    db.ensure_vec_table(768)  # Should not raise
    assert db.get_embedding_dim() == 768


def test_drop_and_recreate_vec_table(db):
    """Test dropping and recreating vec table with different dimension."""
    db.ensure_vec_table(384)
    assert db.has_vec_table()

    db.drop_vec_table()
    assert not db.has_vec_table()

    db.set_embedding_dim(768)
    db._create_vec_table(768)
    assert db.has_vec_table()
    assert db.get_embedding_dim() == 768


def test_insert_vector_noop_without_vec_table(db):
    """Test that insert_vector is a no-op when vec table doesn't exist."""
    raw = RawMemoryInput(title="Test", what="No vec table")
    mem = Memory.from_raw(raw, project="test", file_path="test.md")
    rowid = db.insert_memory(mem)

    # Should not raise, just silently skip
    db.insert_vector(rowid, [0.1] * 768)


def test_vector_search_empty_without_vec_table(db):
    """Test that vector_search returns empty list when vec table doesn't exist."""
    results = db.vector_search([0.1] * 768, limit=10)
    assert results == []


def test_delete_memory_removes_from_all_tables(db, sample_memory, sample_detail):
    """Test that delete_memory removes the memory, its details, and FTS entry."""
    db.insert_memory(sample_memory, details=sample_detail.body)

    deleted = db.delete_memory(sample_memory.id)
    assert deleted is True

    # Memory gone
    assert db.get_memory(sample_memory.id) is None
    # Details gone
    assert db.get_details(sample_memory.id) is None
    # FTS gone
    results = db.fts_search("authentication", limit=10)
    assert len(results) == 0


def test_delete_memory_works_with_prefix(db, sample_memory):
    """Test that delete_memory works with a UUID prefix."""
    db.insert_memory(sample_memory)

    prefix = sample_memory.id[:8]
    deleted = db.delete_memory(prefix)
    assert deleted is True
    assert db.get_memory(sample_memory.id) is None


def test_delete_memory_returns_false_for_nonexistent(db):
    """Test that delete_memory returns False when ID doesn't match."""
    deleted = db.delete_memory("nonexistent-id")
    assert deleted is False


def test_delete_memory_without_details(db, sample_memory):
    """Test that delete works for memories that have no details row."""
    db.insert_memory(sample_memory)

    deleted = db.delete_memory(sample_memory.id)
    assert deleted is True
    assert db.get_memory(sample_memory.id) is None


def test_list_all_for_reindex(db):
    """Test listing all memories for reindex."""
    for i in range(3):
        raw = RawMemoryInput(title=f"Memory {i}", what=f"Content {i}")
        mem = Memory.from_raw(raw, project="test", file_path="test.md")
        db.insert_memory(mem)

    memories = db.list_all_for_reindex()
    assert len(memories) == 3
    assert all("rowid" in m for m in memories)
    assert all("title" in m for m in memories)


def test_updated_count_defaults_to_zero(db, sample_memory):
    """Test that new memories have updated_count = 0."""
    db.insert_memory(sample_memory)
    result = db.get_memory(sample_memory.id)
    assert result["updated_count"] == 0


def test_update_memory_replaces_fields_and_increments_count(db):
    """Test that update_memory replaces fields and increments updated_count."""
    raw = RawMemoryInput(
        title="Original Title",
        what="Original what",
        why="Original why",
        impact="Original impact",
        tags=["tag1"],
        category="decision",
    )
    mem = Memory.from_raw(raw, project="test", file_path="test.md")
    db.insert_memory(mem)

    updated = db.update_memory(
        mem.id,
        what="Updated what",
        why="Updated why",
        impact="Updated impact",
        tags=["tag1", "tag2"],
        details_append="--- 2026-02-16 ---\nNew details here",
    )
    assert updated is True

    result = db.get_memory(mem.id)
    assert result["what"] == "Updated what"
    assert result["why"] == "Updated why"
    assert result["impact"] == "Updated impact"
    assert result["updated_count"] == 1
    assert json.loads(result["tags"]) == ["tag1", "tag2"]


def test_update_memory_appends_details(db):
    """Test that update_memory appends to existing details."""
    raw = RawMemoryInput(
        title="Memory with Details",
        what="Has details",
        category="bug",
    )
    mem = Memory.from_raw(raw, project="test", file_path="test.md")
    db.insert_memory(mem, details="Original details")

    db.update_memory(
        mem.id,
        details_append="--- 2026-02-16 ---\nAppended details",
    )

    detail = db.get_details(mem.id)
    assert "Original details" in detail.body
    assert "Appended details" in detail.body


def test_update_memory_returns_false_for_nonexistent(db):
    """Test that update_memory returns False for unknown IDs."""
    result = db.update_memory("nonexistent-id", what="new")
    assert result is False
