"""Global hotkey handling via the `keyboard` library.

Supports two modes:
  hold   — activate on key down, deactivate on key up (push-to-talk)
  toggle — tap once to start, tap again to stop

`stop()` unhooks the OS-level listeners entirely, so a disabled GPTalks does
no keyboard processing at all (not just ignoring events).
"""

from __future__ import annotations

from typing import Callable, List

import keyboard


class HotkeyListener:
    def __init__(
        self,
        key: str,
        mode: str,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ):
        if mode not in ("hold", "toggle"):
            raise ValueError(f"hotkey mode must be 'hold' or 'toggle', got {mode!r}")
        self.key = key
        self.mode = mode
        self.on_activate = on_activate
        self.on_deactivate = on_deactivate
        self._handles: List[object] = []
        self._active = False  # logical state: are we currently dictating?
        self._key_down = False  # physical state: filters Windows key auto-repeat

    @property
    def is_listening(self) -> bool:
        return bool(self._handles)

    def start(self) -> None:
        if self._handles:
            return
        self._active = False
        self._key_down = False
        self._handles.append(keyboard.on_press_key(self.key, self._on_press, suppress=False))
        self._handles.append(keyboard.on_release_key(self.key, self._on_release, suppress=False))

    def stop(self) -> None:
        for handle in self._handles:
            keyboard.unhook(handle)
        self._handles = []
        self._active = False
        self._key_down = False

    def _on_press(self, _event) -> None:
        # Holding a key makes Windows fire repeated key-down events; only the
        # first one counts.
        if self._key_down:
            return
        self._key_down = True
        if self.mode == "toggle":
            self._active = not self._active
            (self.on_activate if self._active else self.on_deactivate)()
        else:
            self._active = True
            self.on_activate()

    def _on_release(self, _event) -> None:
        self._key_down = False
        if self.mode == "hold" and self._active:
            self._active = False
            self.on_deactivate()
