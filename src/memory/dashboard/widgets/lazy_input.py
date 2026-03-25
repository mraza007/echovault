"""Input widget that only consumes keys when explicitly activated."""

from __future__ import annotations

from textual.events import Focus, Key
from textual.widgets import Input


class LazyInput(Input):
    """An Input that ignores keypresses until explicitly focused via action."""

    _activated = False

    def activate(self) -> None:
        self._activated = True
        self.focus()

    def deactivate(self) -> None:
        self._activated = False

    async def _on_key(self, event: Key) -> None:
        if not self._activated:
            return  # Let the key bubble up to the app
        await super()._on_key(event)

    def _on_focus(self, event: Focus) -> None:  # type: ignore[override]
        if not self._activated:
            self.app.set_focus(None)
            return
        super()._on_focus(event)
