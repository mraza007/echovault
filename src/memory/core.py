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
import sys
from datetime import date
from typing import Optional

from memory.config import get_memory_home, load_config
from memory.db import DimensionMismatchError, MemoryDB
from memory.embeddings.base import EmbeddingProvider
from memory.markdown import write_session_memory
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

    def close(self) -> None:
        """Close database connection and clean up resources."""
        self.db.close()
