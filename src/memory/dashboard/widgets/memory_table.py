"""DataTable subclass with vim-style j/k/G/g navigation."""

from __future__ import annotations

from textual.widgets import DataTable


class VimDataTable(DataTable):
    """DataTable with vim keybindings for row navigation."""

    DEFAULT_CSS = """
    VimDataTable {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True

    def key_j(self) -> None:
        self.action_cursor_down()

    def key_k(self) -> None:
        self.action_cursor_up()

    def key_G(self) -> None:  # noqa: N802
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)

    def key_g(self) -> None:
        if self.row_count > 0:
            self.move_cursor(row=0)
