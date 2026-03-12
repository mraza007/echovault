"""Tests for markdown session file rendering and writing."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from memory.markdown import render_section, write_session_memory
from memory.models import Memory


@pytest.fixture
def sample_memory() -> Memory:
    """Create a sample memory for testing."""
    return Memory(
        id="test-123",
        title="Use FastAPI for API endpoints",
        what="Implemented REST API using FastAPI framework",
        why="FastAPI provides automatic validation and documentation",
        impact="Reduces boilerplate code by 40%",
        tags=["api", "fastapi"],
        category="decision",
        project="my-project",
        source="claude-code",
        related_files=["/src/api/main.py"],
        file_path="2026-01-22-session.md",
        section_anchor="use-fastapi-for-api-endpoints",
        created_at="2026-01-22T14:30:00Z",
        updated_at="2026-01-22T14:30:00Z",
    )


@pytest.fixture
def minimal_memory() -> Memory:
    """Create a minimal memory without optional fields."""
    return Memory(
        id="test-456",
        title="Basic memory",
        what="Simple memory entry",
        why=None,
        impact=None,
        tags=["test"],
        category="context",
        project="my-project",
        source=None,
        related_files=[],
        file_path="2026-01-22-session.md",
        section_anchor="basic-memory",
        created_at="2026-01-22T14:30:00Z",
        updated_at="2026-01-22T14:30:00Z",
    )


class TestRenderSection:
    """Tests for render_section function."""

    def test_render_section_all_fields(self, sample_memory: Memory) -> None:
        """Test rendering section with all fields populated."""
        result = render_section(sample_memory)

        assert "### Use FastAPI for API endpoints" in result
        assert "**What:** Implemented REST API using FastAPI framework" in result
        assert "**Why:** FastAPI provides automatic validation and documentation" in result
        assert "**Impact:** Reduces boilerplate code by 40%" in result
        assert "**Source:** claude-code" in result
        assert "<details>" not in result

    def test_render_section_with_details(self, sample_memory: Memory) -> None:
        """Test rendering section with details tag."""
        details = "Here is the full implementation:\n\n```python\nfrom fastapi import FastAPI\n```"
        result = render_section(sample_memory, details=details)

        assert "### Use FastAPI for API endpoints" in result
        assert "<details>" in result
        assert details in result
        assert "</details>" in result

    def test_render_section_without_optional_fields(self, minimal_memory: Memory) -> None:
        """Test rendering section without Why, Impact, and Source."""
        result = render_section(minimal_memory)

        assert "### Basic memory" in result
        assert "**What:** Simple memory entry" in result
        assert "**Why:**" not in result
        assert "**Impact:**" not in result
        assert "**Source:**" not in result
        assert "<details>" not in result


class TestWriteSessionMemory:
    """Tests for write_session_memory function."""

    @pytest.fixture
    def temp_vault(self) -> str:
        """Create temporary vault directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test-vault" / "my-project"
            vault_path.mkdir(parents=True)
            yield str(vault_path)

    def test_write_creates_new_session_file(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test creating a new session file with correct structure."""
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        assert os.path.exists(file_path)
        assert file_path.endswith("2026-01-22-session.md")

        content = Path(file_path).read_text()

        # Check frontmatter
        assert "---" in content
        assert "project: my-project" in content
        assert "sources: [claude-code]" in content
        assert "created:" in content
        assert "tags: [api, fastapi]" in content

        # Check H1
        assert "# 2026-01-22 Session" in content

        # Check category H2
        assert "## Decisions" in content

        # Check memory section
        assert "### Use FastAPI for API endpoints" in content
        assert "**What:** Implemented REST API using FastAPI framework" in content

    def test_write_appends_to_existing_same_category(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test appending to existing session under same category."""
        # Create initial file
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        # Create second memory in same category
        memory2 = Memory(
            id="test-789",
            title="Another decision",
            what="Made another decision",
            why=None,
            impact=None,
            tags=["decision"],
            category="decision",
            project="my-project",
            source="claude-code",
            related_files=[],
            file_path="2026-01-22-session.md",
            section_anchor="another-decision",
            created_at="2026-01-22T15:00:00Z",
            updated_at="2026-01-22T15:00:00Z",
        )

        file_path2 = write_session_memory(temp_vault, memory2, "2026-01-22")
        assert file_path == file_path2

        content = Path(file_path).read_text()

        # Should have only one "## Decisions" heading
        assert content.count("## Decisions") == 1

        # Should have both memories
        assert "### Use FastAPI for API endpoints" in content
        assert "### Another decision" in content

    def test_write_appends_different_category(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test appending with different category creates new H2."""
        # Create initial file with decision
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        # Create memory with different category
        memory2 = Memory(
            id="test-999",
            title="Bug fix description",
            what="Fixed a critical bug",
            why="Bug was causing crashes",
            impact="Improved stability",
            tags=["bugfix"],
            category="bug",
            project="my-project",
            source="claude-code",
            related_files=[],
            file_path="2026-01-22-session.md",
            section_anchor="bug-fix-description",
            created_at="2026-01-22T15:30:00Z",
            updated_at="2026-01-22T15:30:00Z",
        )

        write_session_memory(temp_vault, memory2, "2026-01-22")

        content = Path(file_path).read_text()

        # Should have both category headings
        assert "## Decisions" in content
        assert "## Bugs Fixed" in content

        # Check category order (Decisions before Bugs Fixed)
        decisions_pos = content.index("## Decisions")
        bugs_pos = content.index("## Bugs Fixed")
        assert decisions_pos < bugs_pos

    def test_write_updates_frontmatter_tags(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test that tags are merged, deduplicated, and sorted."""
        # Create initial file
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        # Create memory with overlapping and new tags
        memory2 = Memory(
            id="test-111",
            title="New pattern",
            what="Discovered a pattern",
            why=None,
            impact=None,
            tags=["api", "pattern", "architecture"],  # "api" overlaps
            category="pattern",
            project="my-project",
            source="claude-code",
            related_files=[],
            file_path="2026-01-22-session.md",
            section_anchor="new-pattern",
            created_at="2026-01-22T16:00:00Z",
            updated_at="2026-01-22T16:00:00Z",
        )

        write_session_memory(temp_vault, memory2, "2026-01-22")

        content = Path(file_path).read_text()

        # Tags should be merged, deduplicated, and sorted
        assert "tags: [api, architecture, fastapi, pattern]" in content

    def test_write_updates_frontmatter_sources(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test that sources list is updated when multiple agents contribute."""
        # Create initial file
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        # Create memory from different source
        memory2 = Memory(
            id="test-222",
            title="Manual entry",
            what="Manually added memory",
            why=None,
            impact=None,
            tags=["manual"],
            category="context",
            project="my-project",
            source="user",
            related_files=[],
            file_path="2026-01-22-session.md",
            section_anchor="manual-entry",
            created_at="2026-01-22T17:00:00Z",
            updated_at="2026-01-22T17:00:00Z",
        )

        write_session_memory(temp_vault, memory2, "2026-01-22")

        content = Path(file_path).read_text()

        # Sources should include both
        assert "sources: [claude-code, user]" in content

    def test_write_with_details(self, temp_vault: str, sample_memory: Memory) -> None:
        """Test writing memory with details section."""
        details = "Full implementation details here"
        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22", details=details)

        content = Path(file_path).read_text()

        assert "<details>" in content
        assert details in content
        assert "</details>" in content

    def test_write_maintains_category_order(self, temp_vault: str) -> None:
        """Test that categories are inserted in correct order."""
        # Create memories in reverse order
        learning_mem = Memory(
            id="l1", title="L", what="Learning", why=None, impact=None,
            tags=[], category="learning", project="my-project", source="claude-code",
            related_files=[], file_path="", section_anchor="l",
            created_at="2026-01-22T10:00:00Z", updated_at="2026-01-22T10:00:00Z",
        )

        decision_mem = Memory(
            id="d1", title="D", what="Decision", why=None, impact=None,
            tags=[], category="decision", project="my-project", source="claude-code",
            related_files=[], file_path="", section_anchor="d",
            created_at="2026-01-22T10:00:00Z", updated_at="2026-01-22T10:00:00Z",
        )

        pattern_mem = Memory(
            id="p1", title="P", what="Pattern", why=None, impact=None,
            tags=[], category="pattern", project="my-project", source="claude-code",
            related_files=[], file_path="", section_anchor="p",
            created_at="2026-01-22T10:00:00Z", updated_at="2026-01-22T10:00:00Z",
        )

        # Write in non-standard order
        file_path = write_session_memory(temp_vault, learning_mem, "2026-01-22")
        write_session_memory(temp_vault, decision_mem, "2026-01-22")
        write_session_memory(temp_vault, pattern_mem, "2026-01-22")

        content = Path(file_path).read_text()

        # Categories should appear in standard order
        decisions_pos = content.index("## Decisions")
        patterns_pos = content.index("## Patterns")
        learnings_pos = content.index("## Learnings")

        assert decisions_pos < patterns_pos < learnings_pos

    def test_write_uses_utf8_for_unicode_content(
        self, temp_vault: str, sample_memory: Memory
    ) -> None:
        """Test writing Unicode content does not depend on system locale."""
        sample_memory.what = "unicode — кириллица ✓"

        file_path = write_session_memory(temp_vault, sample_memory, "2026-01-22")

        content = Path(file_path).read_text(encoding="utf-8")
        assert "unicode — кириллица ✓" in content

    def test_write_reads_legacy_cp1251_and_rewrites_utf8(self, temp_vault: str) -> None:
        """Test appending to a legacy cp1251 file rewrites it as UTF-8."""
        file_path = Path(temp_vault) / "2026-01-22-session.md"
        legacy_content = """---
project: my-project
sources: [claude-code]
created: 2026-01-22T14:30:00Z
tags: [legacy]
---

# 2026-01-22 Session

## Context

### Legacy entry
**What:** старый текст
**Source:** claude-code
"""
        file_path.write_text(legacy_content, encoding="cp1251")

        memory = Memory(
            id="test-unicode",
            title="Unicode append",
            what="новый текст — ✓",
            why=None,
            impact=None,
            tags=["unicode"],
            category="context",
            project="my-project",
            source="claude-code",
            related_files=[],
            file_path="2026-01-22-session.md",
            section_anchor="unicode-append",
            created_at="2026-01-22T18:00:00Z",
            updated_at="2026-01-22T18:00:00Z",
        )

        write_session_memory(temp_vault, memory, "2026-01-22")

        content = file_path.read_text(encoding="utf-8")
        assert "старый текст" in content
        assert "новый текст — ✓" in content
