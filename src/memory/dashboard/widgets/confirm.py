"""Modal screens: confirm dialog and help overlay."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_HELP_TEXT = """\
EchoVault Dashboard

Navigation
  1 2 3 4    Switch mode (Overview / Memories / Review / Ops)
  :          Command palette
  ?          This help
  q          Quit

Memories
  j / k      Navigate rows
  g / G      Jump to first / last row
  /          Focus search
  e          Edit selected in $EDITOR
  n          New memory in $EDITOR
  a          Archive / restore selected

Review Queue
  j / k      Navigate pairs
  m          Merge right into left
  a          Archive right
  x          Keep separate (ignore pair)

Operations
  i          Import from vault
  R          Reindex embeddings
  r          Refresh all data

Commands (via :)
  :overview  :memories  :review  :ops
  :import    :reindex   :refresh
  :project <name>       :q
"""


class HelpModal(ModalScreen[None]):
    """Help overlay showing all keybindings."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal #help-dialog {
        width: 64;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }

    HelpModal #help-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static(_HELP_TEXT)
            yield Static("Press Esc or ? to close", id="help-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """Simple y/n confirmation modal."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal #confirm-dialog {
        width: 60;
        max-width: 80%;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 2 3;
    }

    ConfirmModal #confirm-message {
        margin-bottom: 1;
    }

    ConfirmModal #confirm-hint {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Confirm"),
        Binding("n", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._message, id="confirm-message")
            yield Static("[y] Confirm    [n] Cancel", id="confirm-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
