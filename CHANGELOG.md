# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and follows semantic versioning.

## [Unreleased]

### Added
- Added a curl-friendly POSIX installer that prefers `uv` or `pipx`, falls back to an isolated virtual environment, and can configure a selected agent and project scope in one command.
- Added guided `memory setup` with installed-agent detection.

### Changed
- `memory setup <agent>` now initializes the memory vault automatically and prints a restart hint.
- Replaced global `pip install` guidance with isolated installation paths and documented the unrelated package occupying the `echovault` name on PyPI.

## [0.5.0] - 2026-07-13

### Added
- Added explicit living-memory types for playbooks, known fixes, constraints, project state, and active work.
- Added task-aware, token-budgeted context packs that combine relevant decisions, unresolved work, active bugs, reusable patterns, and recent memories.
- Added structured playbook fields for triggers, prerequisites, steps, verification, follow-ups, constraints, rejected alternatives, and open questions.
- Added provenance and validity metadata, including confidence, validity windows, commit, branch, structured links, verification timestamps, and supersession.
- Added retrieval evaluation against redacted golden datasets with recall, ranking quality, irrelevant-result rate, latency, and context-token metrics.
- Added relevance calibration sweeps, configurable lexical/vector/hybrid thresholds, explicit empty results, and raw score diagnostics through `--explain`.
- Added local retrieval feedback counters and human-reviewable lifecycle proposals for duplicates, contradictions, stale context, completed follow-ups, and broad session dumps.
- Added `memory doctor` health checks for vault/index drift, vectors, references, lifecycle issues, growth, latency, and configuration risks.
- Added refreshed agent integrations and project-local skills for both Claude Code and Codex, including an agent-level on/off switch.

### Changed
- Reframed EchoVault as a continuously maintained project working model designed to reduce repeated discovery and tool round trips.
- Expanded the README with the living-memory workflow, operational success metrics, evaluation guidance, and real-world redacted dataset curation process.

## [0.4.0] - 2026-03-25

### Changed
- **Rewrote the terminal dashboard in Rust** using ratatui + crossterm, replacing the Python/Textual implementation. The dashboard is now a 3MB standalone binary (`memory-dashboard`) with instant startup, no Python runtime needed at runtime.
- Removed Textual dependency from the Python package — significantly smaller install footprint.
- `memory dashboard` now executes the Rust binary instead of launching a Python TUI.
- k9s-style keyboard-driven navigation: `1`-`4` switch panels, `j`/`k`/`g`/`G` vim nav, `/` search, `:` command palette, `?` help overlay.
- Memory editing opens `$EDITOR` (vim) with the memory as a YAML file.
- Duplicate detection runs in a background thread — UI stays responsive during the O(n²) comparison.
- Added `--version` flag to the CLI.
- Added Project column to the memories table.

### Added
- `dashboard/` directory with Rust source (ratatui, crossterm, rusqlite with bundled SQLite + FTS5).
- Confirmation dialogs (y/n) for destructive actions (merge, archive).
- Toast-style notifications for operation feedback.

### Removed
- Python Textual dashboard package (`src/memory/dashboard/`).
- `textual` dependency from `pyproject.toml`.

## [0.3.0] - 2026-03-25

### Changed
- Intermediate Textual dashboard redesign (superseded by 0.4.0 Rust rewrite).

## [0.2.1] - 2026-03-24

### Changed
- Bumped version for post-release fixes.

## [0.2.0] - 2026-03-24

### Added
- Added `memory dashboard`, a Textual terminal dashboard for vault-wide browsing, editing, archive/restore flows, duplicate review, import, and reindex operations.
- Added archive-aware lifecycle metadata for memories, including archived state and merge provenance.
- Added stable markdown memory IDs so existing session files can be safely edited and rewritten.
- Added dashboard and lifecycle regression coverage for the new TUI and archive/merge flows.

### Changed
- Reworked markdown session handling from append-only helpers into a round-trippable parser/writer that preserves session structure while supporting edits.
- Updated SQLite and search behavior so archived memories are excluded from normal search and listing paths by default.
- Improved `memory import` deduplication to key on `(project, file_path, section_anchor)` and hardened import parsing for legacy/BOM/CRLF markdown.
- Documented the new dashboard command in the README.

### Fixed
- Fixed import behavior for same-title memories across session files.
- Fixed import decoding for legacy cp1251 and UTF-8 BOM/CRLF markdown inputs.
