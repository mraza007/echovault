"""Main dashboard app with panel-based navigation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Checkbox,
    ContentSwitcher,
    Input,
    RichLog,
    Static,
)

from memory.core import MemoryService
from memory.dashboard.editor import edit_memory
from memory.dashboard.widgets.command_bar import CommandBar
from memory.dashboard.widgets.confirm import ConfirmModal, HelpModal
from memory.dashboard.widgets.lazy_input import LazyInput
from memory.dashboard.widgets.header_bar import HeaderBar
from memory.dashboard.widgets.memory_table import VimDataTable
from memory.models import RawMemoryInput

_MODE_HINTS = {
    "overview": "1 Overview  2 Memories  3 Review  4 Ops  r Refresh  : Command  q Quit",
    "memories": "j/k Navigate  e Edit  n New  a Archive  / Search  : Command  q Quit",
    "review": "j/k Navigate  m Merge(R\u2192L)  a Archive Right  x Keep Separate  : Command  q Quit",
    "operations": "i Import  R Reindex  r Refresh  : Command  q Quit",
}

_COMMAND_MAP = {
    "overview": "show_overview",
    "memories": "show_memories",
    "review": "show_review",
    "ops": "show_operations",
    "import": "run_import",
    "reindex": "run_reindex",
    "refresh": "refresh_all",
    "q": "quit",
}


def _stringify_tags(tags: object) -> str:
    if isinstance(tags, str):
        try:
            return ", ".join(json.loads(tags))
        except (json.JSONDecodeError, TypeError):
            return tags
    if isinstance(tags, list):
        return ", ".join(str(tag) for tag in tags)
    return ""


class MemoryDashboardApp(App[None]):
    """Terminal dashboard for memory browsing and administration."""

    CSS = """
    Screen {
        layout: vertical;
    }

    /* --- Overview --- */
    #overview-panel {
        layout: vertical;
        padding: 1 2;
    }
    .stats-row {
        height: auto;
        margin-bottom: 1;
    }
    .stats-panel {
        width: 1fr;
        border: solid $accent;
        padding: 1 2;
        margin: 0 1 0 0;
        height: auto;
    }
    .stats-panel:last-child {
        margin-right: 0;
    }
    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    .panel-body {
        height: auto;
    }

    /* --- Memories --- */
    #memories-panel {
        layout: vertical;
        padding: 1 2;
    }
    #mem-filter-bar {
        height: auto;
        margin-bottom: 1;
    }
    #mem-filter-bar Input {
        width: 1fr;
        margin-right: 1;
    }
    #mem-filter-bar Checkbox {
        width: auto;
        margin-top: 1;
    }
    #mem-summary {
        height: auto;
        color: $text-muted;
        margin-bottom: 0;
    }
    #mem-table {
        height: 2fr;
        border: solid $surface-lighten-1;
    }
    #mem-detail-panel {
        height: 1fr;
        min-height: 8;
        border: solid $accent;
        padding: 1 2;
        margin-top: 1;
    }
    #mem-detail-header {
        text-style: bold;
        color: $accent;
        height: auto;
    }
    #mem-detail-body {
        height: 1fr;
    }

    /* --- Review --- */
    #review-panel {
        layout: vertical;
        padding: 1 2;
    }
    #review-table {
        height: 1fr;
        border: solid $surface-lighten-1;
    }
    #review-compare {
        height: 1fr;
        margin-top: 1;
    }
    .compare-panel {
        width: 1fr;
        border: solid $accent;
        padding: 1 2;
        margin: 0 1 0 0;
    }
    .compare-panel:last-child {
        margin-right: 0;
    }
    .compare-title {
        text-style: bold;
        color: $accent;
        height: auto;
        margin-bottom: 1;
    }
    .compare-body {
        height: 1fr;
    }

    /* --- Operations --- */
    #operations-panel {
        layout: vertical;
        padding: 1 2;
    }
    #ops-actions-box {
        height: auto;
        border: solid $accent;
        padding: 1 2;
        margin-bottom: 1;
    }
    #ops-actions-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #ops-log-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
        padding: 0 2;
    }
    #ops-log {
        height: 1fr;
        border: solid $surface-lighten-1;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "blur_inputs", "Unfocus", priority=True),
        Binding("1", "show_overview", "Overview", priority=True),
        Binding("2", "show_memories", "Memories", priority=True),
        Binding("3", "show_review", "Review", priority=True),
        Binding("4", "show_operations", "Ops", priority=True),
    ]

    active_mode: reactive[str] = reactive("overview")

    def __init__(
        self,
        *,
        service: MemoryService,
        initial_project: Optional[str] = None,
        include_archived: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.initial_project = initial_project or ""
        self.initial_include_archived = include_archived
        self.record_cache: dict[str, dict] = {}
        self.memory_rows: dict[str, dict] = {}
        self.duplicate_rows: list[dict] = []
        self.ignored_pairs: set[tuple[str, str]] = set()
        self.filter_generation = 0
        self.detail_generation = 0

    def compose(self) -> ComposeResult:
        yield HeaderBar()
        with ContentSwitcher(id="switcher", initial="overview-panel"):
            # Overview
            with Vertical(id="overview-panel"):
                with Horizontal(classes="stats-row"):
                    with Vertical(classes="stats-panel"):
                        yield Static("Memories", classes="panel-title")
                        yield Static("", id="ov-counts", classes="panel-body")
                    with Vertical(classes="stats-panel"):
                        yield Static("Categories", classes="panel-title")
                        yield Static("", id="ov-categories", classes="panel-body")
                with Horizontal(classes="stats-row"):
                    with Vertical(classes="stats-panel"):
                        yield Static("Projects", classes="panel-title")
                        yield Static("", id="ov-projects", classes="panel-body")
                    with Vertical(classes="stats-panel"):
                        yield Static("Recent", classes="panel-title")
                        yield Static("", id="ov-recent", classes="panel-body")

            # Memories
            with Vertical(id="memories-panel"):
                with Horizontal(id="mem-filter-bar"):
                    yield LazyInput(placeholder="Search memories", id="mem-search")
                    yield LazyInput(
                        placeholder="Project",
                        id="mem-project",
                        value=self.initial_project,
                    )
                    yield LazyInput(placeholder="Category", id="mem-category")
                    yield Checkbox(
                        "Archived",
                        id="mem-archived",
                        value=self.initial_include_archived,
                    )
                yield Static("", id="mem-summary")
                yield VimDataTable(id="mem-table")
                with Vertical(id="mem-detail-panel"):
                    yield Static("", id="mem-detail-header")
                    yield Static(
                        "Select a memory to preview.", id="mem-detail-body"
                    )

            # Review
            with Vertical(id="review-panel"):
                yield VimDataTable(id="review-table")
                with Horizontal(id="review-compare"):
                    with Vertical(classes="compare-panel"):
                        yield Static(
                            "LEFT", classes="compare-title", id="rev-left-title"
                        )
                        yield Static(
                            "", classes="compare-body", id="rev-left-body"
                        )
                    with Vertical(classes="compare-panel"):
                        yield Static(
                            "RIGHT", classes="compare-title", id="rev-right-title"
                        )
                        yield Static(
                            "", classes="compare-body", id="rev-right-body"
                        )

            # Operations
            with Vertical(id="operations-panel"):
                with Vertical(id="ops-actions-box"):
                    yield Static("Actions", id="ops-actions-title")
                    yield Static(
                        "  [i] Import from vault     [R] Reindex embeddings     [r] Refresh all"
                    )
                yield Static("Log", id="ops-log-title")
                yield RichLog(id="ops-log", highlight=True, markup=True)

        yield CommandBar()

    def on_mount(self) -> None:
        mem_table = self.query_one("#mem-table", VimDataTable)
        mem_table.add_columns("Title", "Category", "Status", "Updated")
        rev_table = self.query_one("#review-table", VimDataTable)
        rev_table.add_columns("Left", "Right", "Project", "Score")

        header = self.query_one(HeaderBar)
        header.project = self.initial_project
        header.mode = "overview"
        self.query_one(CommandBar).hints = _MODE_HINTS["overview"]
        self._refresh_overview()
        # LazyInput starts deactivated, no explicit disable needed

    # --- Mode switching ---

    def watch_active_mode(self, mode: str) -> None:
        self.query_one("#switcher", ContentSwitcher).current = f"{mode}-panel"
        self.query_one(HeaderBar).mode = mode
        self.query_one(CommandBar).hints = _MODE_HINTS.get(mode, "")

    def action_show_overview(self) -> None:
        self.active_mode = "overview"
        self._refresh_overview()

    def action_show_memories(self) -> None:
        self.active_mode = "memories"
        if not self.memory_rows:
            self.refresh_memories()

    def action_show_review(self) -> None:
        self.active_mode = "review"
        self.refresh_duplicates()

    def action_show_operations(self) -> None:
        self.active_mode = "operations"

    def action_refresh_all(self) -> None:
        self.record_cache = {}
        mode = self.active_mode
        if mode == "overview":
            self._refresh_overview()
        elif mode == "memories":
            self.refresh_memories()
        elif mode == "review":
            self.refresh_duplicates()
        self.notify("Refreshed.")

    def action_focus_search(self) -> None:
        if self.active_mode != "memories":
            self.active_mode = "memories"
        self._search_active = True
        for iid in ("#mem-search", "#mem-project", "#mem-category"):
            self.query_one(iid, LazyInput).activate()
        self.query_one("#mem-search", LazyInput).activate()

    def action_open_command(self) -> None:
        self.query_one(CommandBar).activate_command()

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    # --- Command palette ---

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cmd-input":
            cmd_bar = self.query_one(CommandBar)
            command = cmd_bar.command_value
            cmd_bar.deactivate_command()
            self._dispatch_command(command)

    def action_blur_inputs(self) -> None:
        self._search_active = False
        cmd_bar = self.query_one(CommandBar)
        if cmd_bar.is_command_active:
            cmd_bar.deactivate_command()
        for iid in ("#mem-search", "#mem-project", "#mem-category"):
            self.query_one(iid, LazyInput).deactivate()
        self.set_focus(None)

    _search_active = False

    def on_key(self, event) -> None:
        # If user is actively typing in search (pressed / first), let Input handle it
        if self._search_active and isinstance(self.focused, Input):
            return
        # Otherwise, route single-char keys to actions
        key_actions = {
            "q": self.action_quit,
            "r": self.action_refresh_all,
            "e": self.action_edit_memory,
            "n": self.action_new_memory,
            "a": self.action_archive_action,
            "i": self.action_run_import,
            "m": self.action_merge_pair,
            "x": self.action_keep_separate,
        }
        action = key_actions.get(event.key)
        if action:
            event.prevent_default()
            action()
        elif event.key == "slash":
            event.prevent_default()
            self.action_focus_search()
        elif event.key == "colon":
            event.prevent_default()
            self.action_open_command()
        elif event.key == "question_mark":
            event.prevent_default()
            self.action_show_help()

    def _dispatch_command(self, command: str) -> None:
        parts = command.split(None, 1)
        if not parts:
            return
        cmd = parts[0].lstrip(":")
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "project":
            self.initial_project = arg.strip()
            self.query_one(HeaderBar).project = self.initial_project
            self.query_one("#mem-project", Input).value = self.initial_project
            self.notify(f"Project: {self.initial_project or 'all'}")
            return

        action = _COMMAND_MAP.get(cmd)
        if action:
            method = getattr(self, f"action_{action}", None) or getattr(
                self, action, None
            )
            if method:
                method()
        else:
            self.notify(f"Unknown command: {cmd}")

    # --- Filter events ---

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"mem-search", "mem-project", "mem-category"}:
            self._schedule_memory_refresh()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "mem-archived":
            self._schedule_memory_refresh()

    def _schedule_memory_refresh(self) -> None:
        self.filter_generation += 1
        gen = self.filter_generation

        def do_refresh() -> None:
            if gen != self.filter_generation:
                return
            self.refresh_memories()

        self.set_timer(0.12, do_refresh)

    # --- Table events ---

    def on_data_table_row_highlighted(
        self, event: VimDataTable.RowHighlighted
    ) -> None:
        if event.data_table.id == "mem-table" and event.row_key is not None:
            self._schedule_detail(str(event.row_key.value))
        elif event.data_table.id == "review-table" and event.row_key is not None:
            self._show_pair(str(event.row_key.value))

    # --- Data operations ---

    def _refresh_overview(self) -> None:
        project = self.initial_project or None
        stats: dict = self.service.get_dashboard_stats(  # type: ignore[assignment]
            project=project, include_duplicate_candidates=False
        )
        totals: dict = stats.get("totals", {})
        self.query_one("#ov-counts", Static).update(
            "\n".join(
                [
                    f"  Total     {totals.get('total', 0)}",
                    f"  Active    {totals.get('active', 0)}",
                    f"  Archived  {totals.get('archived', 0)}",
                ]
            )
        )
        categories: list[dict] = stats.get("categories", [])[:8]
        if categories:
            max_count = max(c["count"] for c in categories) if categories else 1
            cat_lines = []
            for c in categories:
                name = (c.get("category") or "uncategorized")[:12].ljust(12)
                count = c["count"]
                bar_w = int((count / max_count) * 20) if max_count > 0 else 0
                bar = "#" * bar_w + "." * (20 - bar_w)
                cat_lines.append(f"  {name} [{bar}] {count:>4}")
            self.query_one("#ov-categories", Static).update("\n".join(cat_lines))
        else:
            self.query_one("#ov-categories", Static).update("  No data")

        projects: list[dict] = stats.get("projects", [])[:8]
        if projects:
            proj_lines = [
                f"  {p['project'][:28].ljust(28)} {p['count']:>4}" for p in projects
            ]
            self.query_one("#ov-projects", Static).update("\n".join(proj_lines))
        else:
            self.query_one("#ov-projects", Static).update("  No data")

        recent: list[dict] = stats.get("recent", [])[:8]
        if recent:
            recent_lines = [
                f"  {r.get('title', '')[:50].ljust(50)} {r.get('updated_at', '')[:10]}"
                for r in recent
            ]
            self.query_one("#ov-recent", Static).update("\n".join(recent_lines))
        else:
            self.query_one("#ov-recent", Static).update("  No recent memories")

        self.query_one(HeaderBar).memory_count = totals.get("total", 0)

    def refresh_memories(self) -> None:
        query = self.query_one("#mem-search", Input).value.strip() or None
        project = self.query_one("#mem-project", Input).value.strip() or None
        category = self.query_one("#mem-category", Input).value.strip() or None
        include_archived = self.query_one("#mem-archived", Checkbox).value

        records = self.service.list_memories(
            query=query,
            project=project or self.initial_project or None,
            category=category,
            include_archived=include_archived,
            limit=300,
            use_vectors=False,
        )
        self.memory_rows = {r["id"]: r for r in records}

        table = self.query_one("#mem-table", VimDataTable)
        table.clear()

        proj_label = project or self.initial_project or "all projects"
        cat_label = category or "all categories"
        arch_label = "incl. archived" if include_archived else "active only"
        self.query_one("#mem-summary", Static).update(
            f" {len(records)} memories \u2022 {proj_label} \u2022 {cat_label} \u2022 {arch_label}"
        )

        for r in records:
            table.add_row(
                r["title"],
                r.get("category") or "",
                r.get("status") or "active",
                r.get("updated_at", "")[:10],
                key=r["id"],
            )
        if records:
            self._update_detail(records[0]["id"])
        else:
            self.query_one("#mem-detail-header", Static).update("")
            self.query_one("#mem-detail-body", Static).update("No memories found.")

        self.query_one(HeaderBar).memory_count = len(records)

    def _update_detail(self, memory_id: str) -> None:
        record = self.get_cached_record(memory_id)
        if not record:
            return
        header = (
            f"{record['title']}  \u2502  "
            f"{record.get('category') or 'uncategorized'}  \u2502  "
            f"{record.get('project', '')}"
        )
        self.query_one("#mem-detail-header", Static).update(header)

        lines = []
        what = record.get("what") or ""
        if what:
            lines.append(f"What: {what}")
        why = record.get("why")
        if why:
            lines.append(f"Why:  {why}")
        impact = record.get("impact")
        if impact:
            lines.append(f"Impact: {impact}")
        tags = _stringify_tags(record.get("tags"))
        source = record.get("source") or ""
        meta = []
        if tags:
            meta.append(f"Tags: {tags}")
        if source:
            meta.append(f"Source: {source}")
        if meta:
            lines.append("  ".join(meta))
        details = record.get("details")
        if details:
            lines.append("")
            lines.append(details)
        self.query_one("#mem-detail-body", Static).update(
            "\n".join(lines) if lines else "No details."
        )

    def _schedule_detail(self, memory_id: str) -> None:
        self.detail_generation += 1
        gen = self.detail_generation

        def do() -> None:
            if gen != self.detail_generation:
                return
            self._update_detail(memory_id)

        self.set_timer(0.03, do)

    def refresh_duplicates(self) -> None:
        project = self.initial_project or None
        rows = self.service.find_duplicate_candidates(project=project, limit=100)
        filtered = [
            r
            for r in rows
            if (r["left_id"], r["right_id"]) not in self.ignored_pairs
        ]
        self.duplicate_rows = filtered

        table = self.query_one("#review-table", VimDataTable)
        table.clear()
        for i, row in enumerate(filtered):
            table.add_row(
                row["left_title"],
                row["right_title"],
                row["project"],
                f"{row['score']:.2f}",
                key=f"pair-{i}",
            )
        if filtered:
            self._show_pair("pair-0")
        else:
            self.query_one("#rev-left-title", Static).update("LEFT")
            self.query_one("#rev-left-body", Static).update(
                "No duplicate candidates."
            )
            self.query_one("#rev-right-title", Static).update("RIGHT")
            self.query_one("#rev-right-body", Static).update("")

    def _show_pair(self, pair_key: str) -> None:
        idx = int(pair_key.split("-")[-1])
        if idx < 0 or idx >= len(self.duplicate_rows):
            return
        pair = self.duplicate_rows[idx]
        left = self.get_cached_record(pair["left_id"])
        right = self.get_cached_record(pair["right_id"])
        if left:
            self.query_one("#rev-left-title", Static).update(
                f"LEFT: {left['title']}"
            )
            self.query_one("#rev-left-body", Static).update(
                left.get("what", "")
            )
        if right:
            self.query_one("#rev-right-title", Static).update(
                f"RIGHT: {right['title']}"
            )
            self.query_one("#rev-right-body", Static).update(
                right.get("what", "")
            )

    def get_cached_record(self, memory_id: str) -> Optional[dict]:
        if memory_id not in self.record_cache:
            record = self.service.get_memory_record(memory_id)
            if record:
                self.record_cache[memory_id] = record
        return self.record_cache.get(memory_id)

    # --- Selected helpers ---

    def _selected_memory_id(self) -> Optional[str]:
        table = self.query_one("#mem-table", VimDataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key is not None else None

    def _selected_pair(self) -> Optional[dict]:
        table = self.query_one("#review-table", VimDataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None:
            return None
        idx = int(str(row_key.value).split("-")[-1])
        if 0 <= idx < len(self.duplicate_rows):
            return self.duplicate_rows[idx]
        return None

    # --- Actions ---

    def action_edit_memory(self) -> None:
        if self.active_mode != "memories":
            return
        memory_id = self._selected_memory_id()
        if not memory_id:
            return
        record = self.get_cached_record(memory_id)
        if not record:
            return
        self._open_editor(record=record, memory_id=memory_id)

    def action_new_memory(self) -> None:
        self._open_editor(record=None, memory_id=None)

    def _open_editor(
        self, record: Optional[dict], memory_id: Optional[str]
    ) -> None:
        with self.suspend():
            result = edit_memory(record=record, project=self.initial_project)
        if result is None:
            self.notify("Edit cancelled.")
            return
        try:
            if memory_id:
                self.service.update_memory_record(
                    memory_id,
                    title=result["title"],
                    what=result["what"],
                    why=result.get("why"),
                    impact=result.get("impact"),
                    category=result.get("category"),
                    tags=result.get("tags", []),
                    source=result.get("source"),
                    details=result.get("details"),
                )
                self.record_cache.pop(memory_id, None)
                self.notify(f"Updated: {result['title']}")
            else:
                raw = RawMemoryInput(
                    title=result["title"],
                    what=result["what"],
                    why=result.get("why"),
                    impact=result.get("impact"),
                    tags=result.get("tags", []),
                    category=result.get("category"),
                    details=result.get("details"),
                    source=result.get("source"),
                )
                project = (
                    result.get("project") or self.initial_project or "default"
                )
                self.service.save(raw, project=project)
                self.notify(f"Created: {result['title']}")
            self._log(f"Saved: {result['title']}")
            self.refresh_memories()
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error")

    def action_archive_action(self) -> None:
        if self.active_mode == "memories":
            self._archive_selected_memory()
        elif self.active_mode == "review":
            self._archive_duplicate_right()

    def _archive_selected_memory(self) -> None:
        memory_id = self._selected_memory_id()
        if not memory_id:
            return
        record = self.get_cached_record(memory_id)
        if not record:
            return
        is_archived = record.get("status") == "archived"
        action = "Restore" if is_archived else "Archive"

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                self.record_cache.pop(memory_id, None)
                if is_archived:
                    self.service.restore_memory(memory_id)
                else:
                    self.service.archive_memory(memory_id, reason="dashboard")
                self.notify(f"{action}d: {record['title']}")
                self._log(f"{action}d: {record['title']}")
                self.refresh_memories()
            except Exception as exc:
                self.notify(f"{action} failed: {exc}", severity="error")

        self.push_screen(
            ConfirmModal(f'{action} "{record["title"]}"?'), on_confirm
        )

    def action_merge_pair(self) -> None:
        if self.active_mode != "review":
            return
        pair = self._selected_pair()
        if not pair:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                result: dict = self.service.merge_memories(  # type: ignore[assignment]
                    pair["left_id"], [pair["right_id"]]
                )
                self.notify(f"Merged into {result['id'][:12]}")
                self._log(f"Merged into {result['id'][:12]}")
                self.record_cache = {}
                self.refresh_duplicates()
            except Exception as exc:
                self.notify(f"Merge failed: {exc}", severity="error")

        self.push_screen(
            ConfirmModal(
                f'Merge "{pair["right_title"]}" into "{pair["left_title"]}"?'
            ),
            on_confirm,
        )

    def _archive_duplicate_right(self) -> None:
        pair = self._selected_pair()
        if not pair:
            return

        def on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                self.service.archive_memory(
                    pair["right_id"], reason="duplicate-review"
                )
                self.notify(f"Archived: {pair['right_title']}")
                self._log(f"Archived duplicate: {pair['right_title']}")
                self.record_cache = {}
                self.refresh_duplicates()
            except Exception as exc:
                self.notify(f"Archive failed: {exc}", severity="error")

        self.push_screen(
            ConfirmModal(f'Archive "{pair["right_title"]}"?'), on_confirm
        )

    def action_keep_separate(self) -> None:
        if self.active_mode != "review":
            return
        pair = self._selected_pair()
        if pair:
            self.ignored_pairs.add((pair["left_id"], pair["right_id"]))
            self.notify("Pair ignored.")
            self.refresh_duplicates()

    def action_run_import(self) -> None:
        self.notify("Importing...")
        try:
            data = self.service.import_from_vault()
            msg = f"Import: imported={data['imported']} skipped={data['skipped']}"
            self.notify(msg)
            self._log(msg)
            self.refresh_memories()
        except Exception as exc:
            self.notify(f"Import failed: {exc}", severity="error")

    def action_run_reindex(self) -> None:
        self.notify("Reindexing...")
        try:
            data = self.service.reindex()
            msg = f"Reindex: {data['count']} memories, {data['dim']} dims"
            self.notify(msg)
            self._log(msg)
        except Exception as exc:
            self.notify(f"Reindex failed: {exc}", severity="error")

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")  # noqa: DTZ005
        try:
            self.query_one("#ops-log", RichLog).write(f"{ts}  {message}")
        except Exception:
            pass
