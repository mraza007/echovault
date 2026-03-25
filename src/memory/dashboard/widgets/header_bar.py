"""Custom header bar showing mode, project, and memory count."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class HeaderBar(Widget):
    """Top bar: app name | mode | project | count."""

    DEFAULT_CSS = """
    HeaderBar {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
    }

    HeaderBar .header-app-name {
        width: auto;
        padding: 0 1;
        text-style: bold;
        color: $text;
    }

    HeaderBar .header-mode {
        width: auto;
        padding: 0 1;
        color: $text;
    }

    HeaderBar .header-spacer {
        width: 1fr;
    }

    HeaderBar .header-project {
        width: auto;
        padding: 0 1;
        color: $text;
    }

    HeaderBar .header-count {
        width: auto;
        padding: 0 1;
        color: $text;
    }
    """

    mode: reactive[str] = reactive("overview")
    project: reactive[str] = reactive("")
    memory_count: reactive[int] = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static("EchoVault", classes="header-app-name")
        yield Static(":overview", id="header-mode-label", classes="header-mode")
        yield Static("", classes="header-spacer")
        yield Static("", id="header-project-label", classes="header-project")
        yield Static("", id="header-count-label", classes="header-count")

    def watch_mode(self, value: str) -> None:
        try:
            self.query_one("#header-mode-label", Static).update(f":{value}")
        except Exception:
            pass

    def watch_project(self, value: str) -> None:
        try:
            label = value if value else "all projects"
            self.query_one("#header-project-label", Static).update(label)
        except Exception:
            pass

    def watch_memory_count(self, value: int) -> None:
        try:
            self.query_one("#header-count-label", Static).update(f"{value} memories")
        except Exception:
            pass
