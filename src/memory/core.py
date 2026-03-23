"""Core MemoryService orchestrator for the memory system.

This module provides the main MemoryService class that wires together:
- Configuration loading
- Database operations
- Secret redaction
- Markdown file writing
- Embedding generation
- Hybrid search

All CLI commands use this service as the main entry point.
"""

import json
import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from memory.config import get_memory_home, load_config
from memory.db import DimensionMismatchError, MemoryDB
from memory.embeddings.base import EmbeddingProvider
from memory.markdown import read_markdown_text, write_session_memory
from memory.models import Memory, MemoryDetail, RawMemoryInput
from memory.redaction import load_memoryignore, redact
from memory.search import hybrid_search, tiered_search


class MemoryService:
    """Main orchestrator for memory operations.

    Manages configuration, database, embeddings, redaction, and file writing.
    All operations are coordinated through this service.
    """

    def __init__(self, memory_home: Optional[str] = None):
        """Initialize the memory service.

        Args:
            memory_home: Optional path to memory home directory.
                        If not provided, uses MEMORY_HOME env var or ~/.memory
        """
        self.memory_home = memory_home or get_memory_home()
        self.vault_dir = os.path.join(self.memory_home, "vault")
        self.db_path = os.path.join(self.memory_home, "index.db")
        self.config_path = os.path.join(self.memory_home, "config.yaml")
        self.ignore_path = os.path.join(self.memory_home, ".memoryignore")

        # Ensure vault directory exists
        os.makedirs(self.vault_dir, exist_ok=True)

        # Load configuration and initialize database
        self.config = load_config(self.config_path)
        self.db = MemoryDB(self.db_path)

        # Lazy-load embedding provider (expensive operation)
        self._embedding_provider: Optional[EmbeddingProvider] = None
        self._ignore_patterns: Optional[list[str]] = None
        self._vectors_available: Optional[bool] = None

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Get the embedding provider, lazily initializing if needed.

        Returns:
            Configured embedding provider instance
        """
        if self._embedding_provider is None:
            self._embedding_provider = self._create_embedding_provider()
        return self._embedding_provider

    @property
    def ignore_patterns(self) -> list[str]:
        """Get redaction patterns, lazily loading from .memoryignore if needed.

        Returns:
            List of regex patterns for redaction
        """
        if self._ignore_patterns is None:
            self._ignore_patterns = load_memoryignore(self.ignore_path)
        return self._ignore_patterns

    @property
    def vectors_available(self) -> bool:
        """Check if vector operations are available.

        Returns True if the vec table exists and dimensions match.
        Caches the result after first check.
        """
        if self._vectors_available is None:
            self._vectors_available = self.db.has_vec_table()
        return self._vectors_available

    def _create_embedding_provider(self) -> EmbeddingProvider:
        """Create an embedding provider based on configuration.

        Returns:
            Configured embedding provider instance

        Raises:
            ValueError: If embedding provider is not supported
        """
        provider = self.config.embedding.provider
        if provider == "ollama":
            from memory.embeddings.ollama import OllamaEmbedding
            return OllamaEmbedding(
                model=self.config.embedding.model,
                base_url=self.config.embedding.base_url or "http://localhost:11434",
            )
        elif provider == "openai":
            from memory.embeddings.openai_embed import OpenAIEmbedding
            return OpenAIEmbedding(
                model=self.config.embedding.model,
                api_key=self.config.embedding.api_key,
                base_url=self.config.embedding.base_url,
            )
        raise ValueError(f"Unknown embedding provider: {provider}")

    def _merge_tags(self, existing: list[str], extra: list[str]) -> list[str]:
        combined = existing[:]
        existing_norm = {t.lower() for t in existing}
        for tag in extra:
            if tag.lower() in existing_norm:
                continue
            combined.append(tag)
            existing_norm.add(tag.lower())
        return combined

    def _ensure_vectors(self, embedding: list[float]) -> bool:
        """Ensure the vector table is set up for the given embedding dimension.

        Args:
            embedding: An embedding vector to detect dimension from

        Returns:
            True if vectors are ready, False if dimension mismatch
        """
        dim = len(embedding)
        try:
            self.db.ensure_vec_table(dim)
            self._vectors_available = True
            return True
        except DimensionMismatchError:
            self._vectors_available = False
            return False

    def _details_warnings(self, raw: RawMemoryInput) -> list[str]:
        """Return quality warnings for memory details."""
        warnings: list[str] = []

        details = (raw.details or "").strip()
        category = (raw.category or "").strip().lower()

        if category in {"decision", "bug"} and not details:
            warnings.append(
                f"'{category}' memories should include details. "
                "Capture context, options considered, decision, tradeoffs, and follow-up."
            )
            return warnings

        if not details:
            return warnings

        min_chars = 120
        if len(details) < min_chars:
            warnings.append(
                f"Details are brief ({len(details)} chars). "
                f"Aim for at least {min_chars} chars for future-session context."
            )

        required_sections = [
            "context",
            "options considered",
            "decision",
            "tradeoffs",
            "follow-up",
        ]
        details_lc = details.lower()
        missing = [section for section in required_sections if section not in details_lc]
        if missing:
            warnings.append(
                "Details are missing recommended sections: "
                + ", ".join(missing)
                + "."
            )

        return warnings

    def save(
        self, raw: RawMemoryInput, project: Optional[str] = None
    ) -> dict[str, object]:
        """Save a memory with full pipeline: redact, write markdown, index, embed.

        Args:
            raw: Raw memory input to process and save
            project: Optional project name. If not provided, uses current directory name

        Returns:
            Dictionary with 'id' (memory UUID) and 'file_path' (markdown file path)
        """
        # Use current directory name as project if not specified
        project = project or os.path.basename(os.getcwd())
        today = date.today().isoformat()
        vault_project_dir = os.path.join(self.vault_dir, project)

        # Ensure project directory exists
        os.makedirs(vault_project_dir, exist_ok=True)

        warnings = self._details_warnings(raw)

        # Redact all text fields
        raw.what = redact(raw.what, self.ignore_patterns)
        if raw.why:
            raw.why = redact(raw.why, self.ignore_patterns)
        if raw.impact:
            raw.impact = redact(raw.impact, self.ignore_patterns)
        if raw.details:
            raw.details = redact(raw.details, self.ignore_patterns)

        # --- Dedup check: look for similar existing memory in same project ---
        dedup_query = f"{raw.title} {raw.what}"
        try:
            candidates = self.db.fts_search(dedup_query, limit=5, project=project)
        except Exception:
            candidates = []

        if candidates:
            # Normalize: divide top score by max score across broader search
            broad = candidates
            if len(broad) == 1:
                # Single result — get unfiltered results for normalization
                try:
                    broad = self.db.fts_search(dedup_query, limit=5) or broad
                except Exception:
                    pass
            max_score = max(c["score"] for c in broad) if broad else 0.0
            top = candidates[0]
            normalized = top["score"] / max_score if max_score > 0 else 0.0
            # Also require title similarity (case-insensitive)
            title_match = raw.title.strip().lower() == top["title"].strip().lower()
            if normalized >= 0.7 and title_match:
                # Update existing memory instead of creating duplicate
                existing_id = top["id"]
                existing_file_path = top.get("file_path", "")

                merged_tags = self._merge_tags(
                    json.loads(top["tags"]) if isinstance(top["tags"], str) else (top["tags"] or []),
                    raw.tags,
                )

                details_append = None
                if raw.details:
                    details_append = f"--- updated {today} ---\n{raw.details}"

                self.db.update_memory(
                    memory_id=existing_id,
                    what=raw.what,
                    why=raw.why,
                    impact=raw.impact,
                    tags=merged_tags,
                    details_append=details_append,
                )

                # Re-embed the updated memory (non-fatal)
                try:
                    embed_text = f"{top['title']} {raw.what} {raw.why or ''} {raw.impact or ''} {' '.join(merged_tags)}"
                    embedding = self.embedding_provider.embed(embed_text)
                    if self._ensure_vectors(embedding):
                        # Get rowid for the existing memory
                        cursor = self.db.conn.cursor()
                        cursor.execute("SELECT rowid FROM memories WHERE id = ?", (existing_id,))
                        row = cursor.fetchone()
                        if row:
                            self.db.insert_vector(row["rowid"], embedding)
                except Exception:
                    pass

                return {
                    "id": existing_id,
                    "file_path": existing_file_path,
                    "action": "updated",
                    "warnings": warnings,
                }

        # --- Normal save path: create new memory ---
        # Create memory object with generated metadata
        file_path = os.path.join(vault_project_dir, f"{today}-session.md")
        mem = Memory.from_raw(raw, project=project, file_path=file_path)

        # Write markdown file
        write_session_memory(vault_project_dir, mem, today, details=raw.details)

        # Insert into database
        rowid = self.db.insert_memory(mem, details=raw.details)

        # Generate and store embedding
        embed_text = f"{mem.title} {mem.what} {mem.why or ''} {mem.impact or ''} {' '.join(mem.tags)}"
        try:
            embedding = self.embedding_provider.embed(embed_text)
            if self._ensure_vectors(embedding):
                self.db.insert_vector(rowid, embedding)
            else:
                print(
                    "Warning: vector dimension mismatch. Memory saved without vector. "
                    "Run 'memory reindex' to rebuild.",
                    file=sys.stderr,
                )
        except Exception as e:
            # Embedding failed (provider down, network error, etc.)
            # Memory is still saved to DB and markdown — just no vector
            print(
                f"Warning: embedding failed ({e}). Memory saved without vector.",
                file=sys.stderr,
            )

        return {"id": mem.id, "file_path": file_path, "action": "created", "warnings": warnings}

    def search(
        self,
        query: str,
        limit: int = 5,
        project: Optional[str] = None,
        source: Optional[str] = None,
        use_vectors: bool = True,
    ) -> list[dict]:
        """Search memories using hybrid FTS + vector search.

        Falls back to FTS-only if vectors are unavailable.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 5)
            project: Optional project filter
            source: Optional source filter

        Returns:
            List of search results with scores and metadata
        """
        # FTS-only path when semantic search is disabled
        if not use_vectors:
            return hybrid_search(
                self.db,
                None,
                query,
                limit=limit,
                project=project,
                source=source,
            )

        # Use tiered search: FTS first, embed only if sparse results
        if self.vectors_available:
            try:
                return tiered_search(
                    self.db,
                    self.embedding_provider,
                    query,
                    limit=limit,
                    project=project,
                    source=source,
                )
            except DimensionMismatchError:
                self._vectors_available = False
            except Exception:
                pass

        # Fallback: FTS-only search
        return tiered_search(
            self.db,
            None,
            query,
            limit=limit,
            project=project,
            source=source,
        )

    def _ollama_warm(self) -> bool:
        base_url = self.config.embedding.base_url or "http://localhost:11434"
        try:
            from memory.embeddings.ollama import is_model_loaded
        except Exception:
            return False
        return is_model_loaded(self.config.embedding.model, base_url)

    def _should_use_semantic(self, semantic_mode: str) -> bool:
        if semantic_mode == "never":
            return False
        if semantic_mode == "always":
            return True
        provider = self.config.embedding.provider
        if provider == "ollama":
            return self._ollama_warm()
        return True

    def get_context(
        self,
        limit: int = 10,
        project: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
        semantic_mode: Optional[str] = None,
        topup_recent: Optional[bool] = None,
    ) -> tuple[list[dict], int]:
        """Get memory pointers for context injection.

        Args:
            limit: Maximum number of pointers to return
            project: Optional project filter
            source: Optional source filter
            query: Optional search query for semantic filtering

        Returns:
            Tuple of (list of memory pointer dicts, total count)
        """
        total = self.db.count_memories(project=project, source=source)

        if semantic_mode is None:
            semantic_mode = self.config.context.semantic
        if isinstance(semantic_mode, bool):
            semantic_mode = "always" if semantic_mode else "never"
        if semantic_mode not in {"auto", "always", "never"}:
            semantic_mode = "auto"

        if topup_recent is None:
            topup_recent = self.config.context.topup_recent

        results: list[dict]
        if query:
            use_vectors = self._should_use_semantic(semantic_mode)
            results = self.search(
                query,
                limit=limit,
                project=project,
                source=source,
                use_vectors=use_vectors,
            )
            if topup_recent and len(results) < limit:
                recent = self.db.list_recent(
                    limit=limit, project=project, source=source
                )
                seen = {r["id"] for r in results}
                for r in recent:
                    if r["id"] in seen:
                        continue
                    results.append(r)
                    if len(results) >= limit:
                        break
        else:
            results = self.db.list_recent(limit=limit, project=project, source=source)

        return results, total

    def get_details(self, memory_id: str) -> Optional[MemoryDetail]:
        """Get full details for a memory by ID.

        Args:
            memory_id: UUID of the memory to retrieve details for

        Returns:
            MemoryDetail object if details exist, None otherwise
        """
        return self.db.get_details(memory_id)

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID or prefix.

        Args:
            memory_id: Full UUID or prefix of the memory to delete

        Returns:
            True if deleted, False if not found
        """
        return self.db.delete_memory(memory_id)

    def reindex(self, progress_callback=None) -> dict:
        """Rebuild the vector table with current embedding provider.

        Args:
            progress_callback: Optional callable(current, total) for progress reporting

        Returns:
            Dict with 'count' (memories reindexed), 'dim' (new dimension),
            'model' (embedding model name)
        """
        # Detect dimension from provider
        probe = self.embedding_provider.embed("dimension probe")
        dim = len(probe)

        # Drop and recreate vec table
        self.db.drop_vec_table()
        self.db.set_embedding_dim(dim)
        self.db._create_vec_table(dim)

        # Re-embed all memories
        memories = self.db.list_all_for_reindex()
        total = len(memories)

        for i, mem in enumerate(memories):
            tags = ""
            if mem["tags"]:
                try:
                    tags = " ".join(json.loads(mem["tags"]))
                except (json.JSONDecodeError, TypeError):
                    tags = str(mem["tags"])

            embed_text = (
                f"{mem['title']} {mem['what']} "
                f"{mem['why'] or ''} {mem['impact'] or ''} {tags}"
            )
            embedding = self.embedding_provider.embed(embed_text)
            self.db.insert_vector(mem["rowid"], embedding)

            if progress_callback:
                progress_callback(i + 1, total)

        self._vectors_available = True

        return {
            "count": total,
            "dim": dim,
            "model": self.config.embedding.model,
        }

    # ------------------------------------------------------------------
    # Vault import — parse markdown session files into SQLite index
    # ------------------------------------------------------------------

    _HEADING_TO_CATEGORY: dict[str, str] = {
        "Decisions": "decision",
        "Patterns": "pattern",
        "Bugs Fixed": "bug",
        "Context": "context",
        "Learnings": "learning",
    }

    @staticmethod
    def _normalize_markdown_content(content: str) -> str:
        """Normalize markdown text for line-oriented parsing."""
        return content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _make_section_anchor(title: str, occurrence: int = 1) -> str:
        """Create a stable section anchor, suffixing repeated titles."""
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "memory"
        if occurrence <= 1:
            return base
        return f"{base}-{occurrence}"

    @staticmethod
    def _parse_frontmatter(content: str) -> dict:
        """Extract simple key-value frontmatter from ``---`` fenced block."""
        fm: dict = {}
        normalized = MemoryService._normalize_markdown_content(content)
        if not normalized.startswith("---\n"):
            return fm
        parts = normalized.split("---\n", 2)
        if len(parts) < 3:
            return fm
        for line in parts[1].strip().split("\n"):
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                val = [v.strip() for v in val[1:-1].split(",") if v.strip()]
            fm[key] = val
        return fm

    @classmethod
    def _parse_memories_from_md(cls, filepath: str, project: str) -> list[dict]:
        """Parse H3 sections from a vault session markdown file.

        Each ``### Title`` followed by ``**What:** …`` (and optional
        ``**Why:**``, ``**Impact:**``, ``**Source:**``, ``<details>``)
        becomes one memory dict.
        """
        content = cls._normalize_markdown_content(read_markdown_text(Path(filepath)))
        fm = cls._parse_frontmatter(content)

        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", Path(filepath).stem)
        date_str = date_match.group(1) if date_match else date.today().isoformat()

        memories: list[dict] = []
        current_category: Optional[str] = None
        anchor_counts: dict[str, int] = {}

        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith("## "):
                heading = line[3:].strip()
                current_category = cls._HEADING_TO_CATEGORY.get(heading)

            if line.startswith("### "):
                title = line[4:].strip()
                what: Optional[str] = None
                why: Optional[str] = None
                impact: Optional[str] = None
                source: Optional[str] = None
                details_lines: list[str] = []
                in_details = False

                i += 1
                while i < len(lines) and not lines[i].startswith("### ") and not lines[i].startswith("## "):
                    stripped = lines[i].strip()

                    if stripped == "<details>":
                        in_details = True
                        i += 1
                        continue
                    if stripped == "</details>":
                        in_details = False
                        i += 1
                        continue
                    if in_details:
                        details_lines.append(lines[i])
                        i += 1
                        continue

                    if stripped.startswith("**What:**"):
                        what = stripped[len("**What:**"):].strip()
                    elif stripped.startswith("**Why:**"):
                        why = stripped[len("**Why:**"):].strip()
                    elif stripped.startswith("**Impact:**"):
                        impact = stripped[len("**Impact:**"):].strip()
                    elif stripped.startswith("**Source:**"):
                        source = stripped[len("**Source:**"):].strip()

                    i += 1

                if title and what:
                    base_anchor = cls._make_section_anchor(title)
                    occurrence = anchor_counts.get(base_anchor, 0) + 1
                    anchor_counts[base_anchor] = occurrence
                    fm_tags = fm.get("tags", [])
                    memories.append({
                        "title": title,
                        "what": what,
                        "why": why,
                        "impact": impact,
                        "source": source,
                        "category": current_category,
                        "project": project,
                        "tags": fm_tags if isinstance(fm_tags, list) else [],
                        "date": date_str,
                        "file_path": filepath,
                        "section_anchor": cls._make_section_anchor(title, occurrence),
                        "details": "\n".join(details_lines).strip() or None,
                    })
                continue

            i += 1

        return memories

    def import_from_vault(
        self,
        dry_run: bool = False,
        progress_callback=None,
    ) -> dict:
        """Scan vault/ markdown files and import memories missing from SQLite.

        This bridges the gap for multi-agent setups where new ``.md``
        files arrive via file-sync (e.g. Syncthing) but are not yet in
        the local ``index.db``.

        Deduplication key: ``(project, file_path, section_anchor)``.

        Args:
            dry_run: If True, only report what *would* be imported.
            progress_callback: Optional ``callable(imported, skipped, project, title)``
                called for every memory encountered.

        Returns:
            Dict with ``imported`` (int), ``skipped`` (int), ``projects``
            (list of project names that had new imports).
        """
        if not os.path.isdir(self.vault_dir):
            return {"imported": 0, "skipped": 0, "projects": []}

        # Build set of existing section identities.
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT project, file_path, section_anchor, title FROM memories")
        existing: set[tuple[str, str, str]] = {
            (
                row[0],
                row[1],
                row[2] or self._make_section_anchor(row[3]),
            )
            for row in cursor.fetchall()
        }

        imported = 0
        skipped = 0
        touched_projects: set[str] = set()

        for project_dir in sorted(Path(self.vault_dir).iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue

            project = project_dir.name

            for md_file in sorted(project_dir.glob("*.md")):
                parsed = self._parse_memories_from_md(str(md_file), project)

                for mem_data in parsed:
                    key = (
                        mem_data["project"],
                        mem_data["file_path"],
                        mem_data["section_anchor"],
                    )
                    if key in existing:
                        skipped += 1
                        if progress_callback:
                            progress_callback(imported, skipped, project, mem_data["title"])
                        continue

                    if not dry_run:
                        now = datetime.now(timezone.utc).isoformat()
                        mem = Memory(
                            id=str(uuid.uuid4()),
                            title=mem_data["title"],
                            what=mem_data["what"],
                            why=mem_data["why"],
                            impact=mem_data["impact"],
                            tags=mem_data["tags"],
                            category=mem_data["category"],
                            project=mem_data["project"],
                            source=mem_data["source"],
                            related_files=[],
                            file_path=mem_data["file_path"],
                            section_anchor=mem_data["section_anchor"],
                            created_at=now,
                            updated_at=now,
                        )
                        self.db.insert_memory(mem, details=mem_data.get("details"))
                        existing.add(key)

                    imported += 1
                    touched_projects.add(project)

                    if progress_callback:
                        progress_callback(imported, skipped, project, mem_data["title"])

        return {
            "imported": imported,
            "skipped": skipped,
            "projects": sorted(touched_projects),
        }

    def close(self) -> None:
        """Close database connection and clean up resources."""
        self.db.close()
