"""Tests for the ``memory import`` command and ``import_from_vault`` service method."""

import os
import textwrap
from pathlib import Path

from click.testing import CliRunner

from memory.cli import main
from memory.core import MemoryService


# ---------------------------------------------------------------------------
# Helper: write a minimal vault session file
# ---------------------------------------------------------------------------

def _write_session_md(vault_dir, project, filename, content):
    proj_dir = os.path.join(vault_dir, project)
    os.makedirs(proj_dir, exist_ok=True)
    filepath = os.path.join(proj_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))
    return filepath


def _write_session_md_bytes(vault_dir, project, filename, content_bytes):
    proj_dir = os.path.join(vault_dir, project)
    os.makedirs(proj_dir, exist_ok=True)
    filepath = Path(proj_dir) / filename
    filepath.write_bytes(content_bytes)
    return str(filepath)


# ---------------------------------------------------------------------------
# MemoryService.import_from_vault — unit tests
# ---------------------------------------------------------------------------

class TestImportFromVault:
    """Core import logic tests."""

    def test_import_new_memories(self, env_home):
        """New H3 sections from vault .md files are imported into SQLite."""
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "ProjectA", "2026-03-04-session.md", """\
            ---
            project: ProjectA
            tags: [infra, test]
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Server migration
            **What:** Moved from VM to bare metal.
            **Why:** Better performance.
            **Impact:** 2x throughput.

            ### Database upgrade
            **What:** Upgraded PostgreSQL 14 → 16.
        """)

        svc = MemoryService()
        result = svc.import_from_vault()
        svc.close()

        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert "ProjectA" in result["projects"]

    def test_skip_duplicates(self, env_home):
        """Already-imported memories are skipped on subsequent runs."""
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "ProjB", "2026-03-04-session.md", """\
            ---
            project: ProjB
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Learnings

            ### Lesson one
            **What:** Always check logs first.
        """)

        svc = MemoryService()

        first = svc.import_from_vault()
        assert first["imported"] == 1

        second = svc.import_from_vault()
        assert second["imported"] == 0
        assert second["skipped"] == 1

        svc.close()

    def test_allows_same_title_in_different_session_files(self, env_home):
        """Same-title memories in different session files should both import."""
        vault = os.path.join(str(env_home), "vault")
        for filename, what in [
            ("2026-03-04-session.md", "Updated the Python dependencies."),
            ("2026-03-05-session.md", "Updated the Node dependencies."),
        ]:
            _write_session_md(vault, "ProjDup", filename, f"""\
                ---
                project: ProjDup
                tags: [deps]
                created: 2026-03-04T10:00:00+00:00
                ---

                # Session

                ## Context

                ### Dependency update
                **What:** {what}
            """)

        svc = MemoryService()

        first = svc.import_from_vault()
        second = svc.import_from_vault()
        results = svc.search("Dependency update", limit=10, use_vectors=False)

        assert first["imported"] == 2
        assert second["imported"] == 0
        assert second["skipped"] == 2
        assert len(results) == 2

        svc.close()

    def test_dry_run(self, env_home):
        """Dry run reports counts but does not modify the database."""
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "ProjC", "2026-03-04-session.md", """\
            ---
            project: ProjC
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Dry run test
            **What:** This should not be inserted.
        """)

        svc = MemoryService()
        result = svc.import_from_vault(dry_run=True)
        assert result["imported"] == 1  # counted but not inserted

        # Verify nothing was actually inserted
        total = svc.db.count_memories()
        assert total == 0

        svc.close()

    def test_details_parsed(self, env_home):
        """<details> blocks are captured as memory details."""
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "ProjD", "2026-03-04-session.md", """\
            ---
            project: ProjD
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Bugs Fixed

            ### Connection timeout bug
            **What:** Fixed TCP timeout on high latency links.

            <details>
            Root cause was SO_TIMEOUT set to 5s instead of 30s.
            </details>
        """)

        svc = MemoryService()
        svc.import_from_vault()

        # Verify the memory was imported
        results = svc.search("Connection timeout bug", limit=1, use_vectors=False)
        assert len(results) == 1
        assert results[0]["title"] == "Connection timeout bug"

        # Verify details were captured
        mem_id = results[0]["id"]
        detail = svc.get_details(mem_id)
        assert detail is not None
        assert "SO_TIMEOUT" in detail.body

        svc.close()

    def test_empty_vault(self, env_home):
        """Importing from an empty vault returns zeroes."""
        svc = MemoryService()
        result = svc.import_from_vault()
        assert result["imported"] == 0
        assert result["skipped"] == 0
        svc.close()

    def test_multiple_projects(self, env_home):
        """Memories from multiple vault sub-directories are all imported."""
        vault = os.path.join(str(env_home), "vault")

        _write_session_md(vault, "Alpha", "2026-03-04-session.md", """\
            ---
            project: Alpha
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Alpha memory
            **What:** From project Alpha.
        """)

        _write_session_md(vault, "Beta", "2026-03-04-session.md", """\
            ---
            project: Beta
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Beta memory
            **What:** From project Beta.
        """)

        svc = MemoryService()
        result = svc.import_from_vault()
        svc.close()

        assert result["imported"] == 2
        assert set(result["projects"]) == {"Alpha", "Beta"}

    def test_import_reads_legacy_cp1251_markdown(self, env_home):
        """Import should decode legacy Windows-authored markdown content."""
        vault = os.path.join(str(env_home), "vault")
        content = textwrap.dedent("""\
            ---
            project: LegacyProj
            tags: [legacy]
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Старый импорт
            **What:** старый текст
        """)
        _write_session_md_bytes(
            vault,
            "LegacyProj",
            "2026-03-04-session.md",
            content.encode("cp1251"),
        )

        svc = MemoryService()
        result = svc.import_from_vault()
        recent = svc.db.list_recent(limit=1, project="LegacyProj")
        memory = svc.db.get_memory(recent[0]["id"])

        assert result["imported"] == 1
        assert memory is not None
        assert memory["title"] == "Старый импорт"
        assert memory["what"] == "старый текст"

        svc.close()

    def test_import_parses_utf8_sig_crlf_frontmatter(self, env_home):
        """Import should parse BOM/CRLF frontmatter and keep tags."""
        vault = os.path.join(str(env_home), "vault")
        content = textwrap.dedent("""\
            ---
            project: BomProj
            tags: [infra, sync]
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### CRLF import
            **What:** Frontmatter should still parse.
        """).replace("\n", "\r\n")
        _write_session_md_bytes(
            vault,
            "BomProj",
            "2026-03-04-session.md",
            content.encode("utf-8-sig"),
        )

        svc = MemoryService()
        result = svc.import_from_vault()
        recent = svc.db.list_recent(limit=1, project="BomProj")
        memory = svc.db.get_memory(recent[0]["id"])

        assert result["imported"] == 1
        assert memory is not None
        assert memory["tags"] == '["infra", "sync"]'

        svc.close()


# ---------------------------------------------------------------------------
# CLI: ``memory import`` tests
# ---------------------------------------------------------------------------

class TestImportCLI:
    """Click CLI integration tests."""

    def test_cli_import(self, env_home):
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "CLIProj", "2026-03-04-session.md", """\
            ---
            project: CLIProj
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### CLI import test
            **What:** Testing the CLI command.
        """)

        runner = CliRunner()
        result = runner.invoke(main, ["import"])
        assert result.exit_code == 0
        assert "Imported: 1" in result.output

    def test_cli_import_dry_run(self, env_home):
        vault = os.path.join(str(env_home), "vault")
        _write_session_md(vault, "DryProj", "2026-03-04-session.md", """\
            ---
            project: DryProj
            tags: []
            created: 2026-03-04T10:00:00+00:00
            ---

            # 2026-03-04 Session

            ## Context

            ### Dry run CLI
            **What:** Should not persist.
        """)

        runner = CliRunner()
        result = runner.invoke(main, ["import", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "[new]" in result.output
        assert "Imported: 1" in result.output

        # Verify nothing persisted
        svc = MemoryService()
        assert svc.db.count_memories() == 0
        svc.close()
