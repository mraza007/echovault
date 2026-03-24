"""Textual dashboard for browsing and managing memories."""

from __future__ import annotations

import json
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from memory.core import MemoryService
from memory.models import RawMemoryInput


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

    #overview-content, #detail-panel, #duplicate-detail, #operations-log {
        border: round $surface;
        padding: 1 2;
        height: 1fr;
    }

    #memory-actions, #duplicate-actions, #operations-actions {
        height: auto;
        padding: 1 0;
    }

    #memory-table, #duplicate-table {
        height: 1fr;
    }

    .filters {
        height: auto;
    }

    .editor {
        width: 1fr;
    }

    .column {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "show_overview", "Overview"),
        Binding("2", "show_memories", "Memories"),
        Binding("3", "show_review", "Review"),
        Binding("4", "show_operations", "Ops"),
        Binding("/", "focus_search", "Search"),
        Binding("n", "new_memory", "New"),
        Binding("s", "save_memory", "Save"),
        Binding("a", "archive_selected", "Archive"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("i", "run_import", "Import"),
        Binding("R", "run_reindex", "Reindex"),
        Binding("m", "merge_selected_pair", "Merge"),
    ]

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
        self.memory_rows: dict[str, dict] = {}
        self.duplicate_rows: list[dict] = []
        self.ignored_pairs: set[tuple[str, str]] = set()
        self.editing_memory_id: Optional[str] = None
        self.operation_lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="tabs", initial="overview"):
            with TabPane("Overview", id="overview"):
                yield Static(id="overview-content")
            with TabPane("Memories", id="memories"):
                with Horizontal():
                    with Vertical(classes="column"):
                        with Horizontal(classes="filters"):
                            yield Input(placeholder="Search memories", id="search-input")
                            yield Input(value=self.initial_project, placeholder="Project", id="project-filter")
                            yield Input(placeholder="Category", id="category-filter")
                            yield Checkbox("Archived", value=self.initial_include_archived, id="archived-toggle")
                        yield DataTable(id="memory-table")
                        with Horizontal(id="memory-actions"):
                            yield Button("New", id="new-memory")
                            yield Button("Load Selected", id="load-memory")
                            yield Button("Save", id="save-memory", variant="primary")
                            yield Button("Archive / Restore", id="archive-memory", variant="warning")
                    with Vertical(classes="column editor"):
                        yield Input(placeholder="Title", id="title-input")
                        yield Input(placeholder="Project", id="editor-project-input")
                        yield Input(placeholder="Category", id="editor-category-input")
                        yield Input(placeholder="Tags (comma separated)", id="tags-input")
                        yield Input(placeholder="Source", id="source-input")
                        yield Input(placeholder="What", id="what-input")
                        yield Input(placeholder="Why", id="why-input")
                        yield Input(placeholder="Impact", id="impact-input")
                        yield TextArea(id="details-input")
                        yield Static(id="detail-panel")
            with TabPane("Review Queue", id="review"):
                with Horizontal():
                    with Vertical(classes="column"):
                        yield DataTable(id="duplicate-table")
                        with Horizontal(id="duplicate-actions"):
                            yield Button("Merge Right into Left", id="merge-duplicates", variant="primary")
                            yield Button("Archive Right", id="archive-duplicate", variant="warning")
                            yield Button("Keep Separate", id="ignore-duplicate")
                    yield Static(id="duplicate-detail", classes="column")
            with TabPane("Operations", id="operations"):
                with Horizontal(id="operations-actions"):
                    yield Button("Import", id="run-import", variant="primary")
                    yield Button("Reindex", id="run-reindex", variant="primary")
                    yield Button("Refresh", id="run-refresh")
                yield Static(id="operations-log")
        yield Footer()

    def on_mount(self) -> None:
        memory_table = self.query_one("#memory-table", DataTable)
        memory_table.cursor_type = "row"
        memory_table.zebra_stripes = True
        memory_table.add_columns("Title", "Project", "Category", "Status", "Updated")

        duplicate_table = self.query_one("#duplicate-table", DataTable)
        duplicate_table.cursor_type = "row"
        duplicate_table.zebra_stripes = True
        duplicate_table.add_columns("Left", "Right", "Project", "Score")

        self.action_refresh_all()
        self.action_new_memory()

    def action_show_overview(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "overview"

    def action_show_memories(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "memories"

    def action_show_review(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "review"

    def action_show_operations(self) -> None:
        self.query_one("#tabs", TabbedContent).active = "operations"

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_new_memory(self) -> None:
        self.editing_memory_id = None
        self.query_one("#title-input", Input).value = ""
        self.query_one("#editor-project-input", Input).value = self.initial_project
        self.query_one("#editor-category-input", Input).value = ""
        self.query_one("#tags-input", Input).value = ""
        self.query_one("#source-input", Input).value = ""
        self.query_one("#what-input", Input).value = ""
        self.query_one("#why-input", Input).value = ""
        self.query_one("#impact-input", Input).value = ""
        self.query_one("#details-input", TextArea).text = ""
        self.query_one("#detail-panel", Static).update("Creating a new memory.")
        self.action_show_memories()

    def action_save_memory(self) -> None:
        self._save_editor_memory()

    def action_archive_selected(self) -> None:
        self._archive_or_restore_selected()

    def action_merge_selected_pair(self) -> None:
        self._merge_selected_pair()

    def action_run_import(self) -> None:
        self._run_import()

    def action_run_reindex(self) -> None:
        self._run_reindex()

    def action_refresh_all(self) -> None:
        self._refresh_overview()
        self._refresh_memories()
        self._refresh_duplicates()
        self._append_log("Refreshed dashboard.")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"search-input", "project-filter", "category-filter"}:
            self._refresh_memories()
            self._refresh_duplicates()
            self._refresh_overview()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "archived-toggle":
            self._refresh_memories()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "new-memory": self.action_new_memory,
            "load-memory": self._load_selected_memory,
            "save-memory": self._save_editor_memory,
            "archive-memory": self._archive_or_restore_selected,
            "merge-duplicates": self._merge_selected_pair,
            "archive-duplicate": self._archive_duplicate_right,
            "ignore-duplicate": self._ignore_duplicate_pair,
            "run-import": self._run_import,
            "run-reindex": self._run_reindex,
            "run-refresh": self.action_refresh_all,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "memory-table":
            memory_id = str(event.row_key)
            self._update_memory_detail(memory_id)
        elif event.data_table.id == "duplicate-table":
            self._update_duplicate_detail(str(event.row_key))

    def _refresh_overview(self) -> None:
        stats = self.service.get_dashboard_stats(project=self._project_filter() or None)
        lines = [
            f"Total memories: {stats['totals'].get('total', 0)}",
            f"Active: {stats['totals'].get('active', 0)}",
            f"Archived: {stats['totals'].get('archived', 0)}",
            f"Duplicate candidates: {stats['duplicate_candidates']}",
            "",
            "Projects:",
        ]
        lines.extend(
            f"- {item['project']}: {item['count']}"
            for item in stats["projects"][:10]
        )
        lines.append("")
        lines.append("Categories:")
        lines.extend(
            f"- {item['category'] or 'uncategorized'}: {item['count']}"
            for item in stats["categories"][:10]
        )
        self.query_one("#overview-content", Static).update("\n".join(lines))

    def _refresh_memories(self) -> None:
        records = self.service.list_memories(
            query=self.query_one("#search-input", Input).value.strip() or None,
            project=self._project_filter() or None,
            category=self.query_one("#category-filter", Input).value.strip() or None,
            include_archived=self.query_one("#archived-toggle", Checkbox).value,
            limit=300,
        )
        self.memory_rows = {record["id"]: record for record in records}
        table = self.query_one("#memory-table", DataTable)
        table.clear()
        for record in records:
            table.add_row(
                record["title"],
                record["project"],
                record.get("category") or "",
                record.get("status") or "active",
                record.get("updated_at", "")[:10],
                key=record["id"],
            )
        if records:
            self._update_memory_detail(records[0]["id"])
        else:
            self.query_one("#detail-panel", Static).update("No memories found.")

    def _refresh_duplicates(self) -> None:
        project = self._project_filter() or None
        rows = [
            row
            for row in self.service.find_duplicate_candidates(project=project, limit=100)
            if (row["left_id"], row["right_id"]) not in self.ignored_pairs
        ]
        self.duplicate_rows = rows
        table = self.query_one("#duplicate-table", DataTable)
        table.clear()
        for index, row in enumerate(rows):
            key = f"pair-{index}"
            table.add_row(
                row["left_title"],
                row["right_title"],
                row["project"],
                f"{row['score']:.2f}",
                key=key,
            )
        if rows:
            self._update_duplicate_detail("pair-0")
        else:
            self.query_one("#duplicate-detail", Static).update("No duplicate candidates.")

    def _selected_memory_id(self) -> Optional[str]:
        table = self.query_one("#memory-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key) if row_key is not None else None

    def _selected_duplicate_pair(self) -> Optional[dict]:
        table = self.query_one("#duplicate-table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        if row_key is None:
            return None
        index = int(str(row_key).split("-")[-1])
        if 0 <= index < len(self.duplicate_rows):
            return self.duplicate_rows[index]
        return None

    def _update_memory_detail(self, memory_id: str) -> None:
        record = self.service.get_memory_record(memory_id)
        if not record:
            self.query_one("#detail-panel", Static).update("No memory selected.")
            return
        self.query_one("#detail-panel", Static).update(
            "\n".join(
                [
                    f"ID: {record['id'][:12]}",
                    f"Project: {record['project']}",
                    f"Category: {record.get('category') or ''}",
                    f"Status: {record.get('status') or 'active'}",
                    f"Source: {record.get('source') or ''}",
                    f"Tags: {_stringify_tags(record.get('tags'))}",
                    "",
                    record["what"],
                    record.get("details", ""),
                ]
            ).strip()
        )

    def _update_duplicate_detail(self, pair_key: str) -> None:
        index = int(pair_key.split("-")[-1])
        pair = self.duplicate_rows[index]
        left = self.service.get_memory_record(pair["left_id"])
        right = self.service.get_memory_record(pair["right_id"])
        detail = [
            f"Project: {pair['project']}",
            f"Score: {pair['score']:.2f}",
            "",
            f"Left: {left['title']}",
            left["what"],
            "",
            f"Right: {right['title']}",
            right["what"],
        ]
        self.query_one("#duplicate-detail", Static).update("\n".join(detail))

    def _load_selected_memory(self) -> None:
        memory_id = self._selected_memory_id()
        if not memory_id:
            return
        record = self.service.get_memory_record(memory_id)
        if not record:
            return
        self.editing_memory_id = record["id"]
        self.query_one("#title-input", Input).value = record["title"]
        self.query_one("#editor-project-input", Input).value = record["project"]
        self.query_one("#editor-category-input", Input).value = record.get("category") or ""
        self.query_one("#tags-input", Input).value = _stringify_tags(record.get("tags"))
        self.query_one("#source-input", Input).value = record.get("source") or ""
        self.query_one("#what-input", Input).value = record["what"]
        self.query_one("#why-input", Input).value = record.get("why") or ""
        self.query_one("#impact-input", Input).value = record.get("impact") or ""
        self.query_one("#details-input", TextArea).text = record.get("details", "")
        self._update_memory_detail(memory_id)

    def _save_editor_memory(self) -> None:
        title = self.query_one("#title-input", Input).value.strip()
        project = self.query_one("#editor-project-input", Input).value.strip() or self.initial_project or "default"
        category = self.query_one("#editor-category-input", Input).value.strip() or None
        tags = [tag.strip() for tag in self.query_one("#tags-input", Input).value.split(",") if tag.strip()]
        source = self.query_one("#source-input", Input).value.strip() or None
        what = self.query_one("#what-input", Input).value.strip()
        why = self.query_one("#why-input", Input).value.strip() or None
        impact = self.query_one("#impact-input", Input).value.strip() or None
        details = self.query_one("#details-input", TextArea).text.strip() or None

        if not title or not what:
            self._append_log("Title and What are required.")
            return

        try:
            if self.editing_memory_id:
                result = self.service.update_memory_record(
                    self.editing_memory_id,
                    title=title,
                    what=what,
                    why=why,
                    impact=impact,
                    category=category,
                    tags=tags,
                    source=source,
                    details=details,
                )
            else:
                raw = RawMemoryInput(
                    title=title,
                    what=what,
                    why=why,
                    impact=impact,
                    tags=tags,
                    category=category,
                    details=details,
                    source=source,
                )
                result = self.service.save(raw, project=project)
                self.editing_memory_id = result["id"]
            self._append_log(f"{result['action'].title()}: {title}")
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Save failed: {exc}")

    def _archive_or_restore_selected(self) -> None:
        memory_id = self._selected_memory_id()
        if not memory_id:
            return
        record = self.service.get_memory_record(memory_id)
        if not record:
            return
        try:
            if record.get("status") == "archived":
                result = self.service.restore_memory(memory_id)
            else:
                result = self.service.archive_memory(memory_id, reason="dashboard")
            self._append_log(f"{result['action'].title()}: {record['title']}")
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Archive failed: {exc}")

    def _merge_selected_pair(self) -> None:
        pair = self._selected_duplicate_pair()
        if not pair:
            return
        try:
            result = self.service.merge_memories(pair["left_id"], [pair["right_id"]])
            self._append_log(f"Merged 1 memory into {result['id'][:12]}")
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Merge failed: {exc}")

    def _archive_duplicate_right(self) -> None:
        pair = self._selected_duplicate_pair()
        if not pair:
            return
        try:
            result = self.service.archive_memory(pair["right_id"], reason="duplicate-review")
            self._append_log(f"Archived duplicate: {result['id'][:12]}")
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Archive duplicate failed: {exc}")

    def _ignore_duplicate_pair(self) -> None:
        pair = self._selected_duplicate_pair()
        if not pair:
            return
        self.ignored_pairs.add((pair["left_id"], pair["right_id"]))
        self._append_log(f"Ignored pair: {pair['left_title']} / {pair['right_title']}")
        self._refresh_duplicates()

    def _run_import(self) -> None:
        try:
            result = self.service.import_from_vault()
            self._append_log(
                f"Import complete: imported={result['imported']} skipped={result['skipped']}"
            )
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Import failed: {exc}")

    def _run_reindex(self) -> None:
        try:
            result = self.service.reindex()
            self._append_log(
                f"Reindex complete: {result['count']} memories, {result['dim']} dims"
            )
            self.action_refresh_all()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            self._append_log(f"Reindex failed: {exc}")

    def _append_log(self, message: str) -> None:
        self.operation_lines.append(message)
        self.query_one("#operations-log", Static).update("\n".join(self.operation_lines))

    def _project_filter(self) -> str:
        return self.query_one("#project-filter", Input).value.strip()
