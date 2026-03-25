"""Bottom command bar with context-sensitive key hints and : command input."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static


class CommandBar(Widget):
    """Bottom bar: key hints or : command input."""

    DEFAULT_CSS = """
    CommandBar {
        dock: bottom;
        height: auto;
        max-height: 2;
        background: $surface;
    }

    CommandBar #cmd-hints {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    CommandBar #cmd-input {
        display: none;
        height: 1;
    }

    CommandBar.--command-active #cmd-hints {
        display: none;
    }

    CommandBar.--command-active #cmd-input {
        display: block;
    }
    """

    hints: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static("", id="cmd-hints")
        yield Input(placeholder=":", id="cmd-input")

    def watch_hints(self, value: str) -> None:
        try:
            self.query_one("#cmd-hints", Static).update(value)
        except Exception:
            pass

    def activate_command(self) -> None:
        self.add_class("--command-active")
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""
        inp.focus()

    def deactivate_command(self) -> None:
        self.remove_class("--command-active")
        self.query_one("#cmd-input", Input).value = ""

    @property
    def is_command_active(self) -> bool:
        return self.has_class("--command-active")

    @property
    def command_value(self) -> str:
        return self.query_one("#cmd-input", Input).value.strip()
