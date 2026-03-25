# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and follows semantic versioning.

## [Unreleased]

## [0.3.0] - 2026-03-25

### Changed
- Redesigned the terminal dashboard with k9s-style keyboard-driven navigation — number keys switch between panels instantly, no more tab switching.
- Replaced horizontal split layout with vertical table-on-top, detail-preview-on-bottom for the memories view.
- Memory editing now opens `$EDITOR` (defaults to vim) with the memory as a YAML file instead of an in-app form editor.
- Added vim-style `j`/`k`/`g`/`G` navigation in all data tables.
- Added `:` command palette for power-user operations (`:import`, `:reindex`, `:project <name>`, etc.).
- Added `?` help overlay showing all keybindings.
- Added confirmation dialogs for destructive actions (merge, archive).
- Replaced operations buttons with keyboard shortcut hints and `RichLog` for timestamped operation output.
- Operation feedback now uses toast notifications instead of requiring a switch to the operations panel.
- Added custom header bar showing current mode, active project filter, and memory count.
- Added context-sensitive key hints in the bottom command bar that update per panel.
- Refactored dashboard from a single 706-line file into a modular `dashboard/` package (app, widgets, editor).

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

