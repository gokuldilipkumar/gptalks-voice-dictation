"""System tray icon with per-state visuals and the app menu.

Icons are drawn programmatically with Pillow (a mic glyph on a colored disc):
  gray  — idle, waiting for the hotkey
  red   — recording
  amber — transcribing
"""

from __future__ import annotations

from enum import Enum
from typing import Callable

import pystray
from PIL import Image, ImageDraw


class State(Enum):
    IDLE = "Idle"
    RECORDING = "Recording"
    TRANSCRIBING = "Transcribing"


_STATE_COLORS = {
    State.IDLE: (100, 100, 108),
    State.RECORDING: (214, 48, 49),
    State.TRANSCRIBING: (230, 168, 23),
}


def _make_icon(color: tuple) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 2, size - 2], fill=color + (255,))
    white = (255, 255, 255, 255)
    # Microphone glyph: capsule body, cradle arc, stem, base.
    d.rounded_rectangle([26, 12, 38, 34], radius=6, fill=white)
    d.arc([20, 20, 44, 42], start=0, end=180, fill=white, width=3)
    d.line([32, 42, 32, 48], fill=white, width=3)
    d.line([25, 49, 39, 49], fill=white, width=3)
    return img


class TrayApp:
    def __init__(
        self,
        is_enabled: Callable[[], bool],
        on_toggle_enabled: Callable[[], None],
        is_cleanup_on: Callable[[], bool],
        on_toggle_cleanup: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._icons = {state: _make_icon(color) for state, color in _STATE_COLORS.items()}
        menu = pystray.Menu(
            pystray.MenuItem(
                "Enabled",
                lambda *_: on_toggle_enabled(),
                checked=lambda item: is_enabled(),
            ),
            pystray.MenuItem(
                "Cleanup transcripts",
                lambda *_: on_toggle_cleanup(),
                checked=lambda item: is_cleanup_on(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open settings", lambda *_: on_open_settings()),
            pystray.MenuItem("Quit", lambda *_: on_quit()),
        )
        self._icon = pystray.Icon(
            "GPTalks",
            icon=self._icons[State.IDLE],
            title="GPTalks — Idle",
            menu=menu,
        )

    def set_state(self, state: State) -> None:
        self._icon.icon = self._icons[state]
        self._icon.title = f"GPTalks — {state.value}"

    def run(self) -> None:
        """Blocks until stop() is called. Must run on the main thread."""
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()
