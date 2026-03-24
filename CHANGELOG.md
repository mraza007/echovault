# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and follows semantic versioning.

## [Unreleased]

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

