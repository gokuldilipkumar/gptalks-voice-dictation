"""Global hotkey handling via the `keyboard` library.

Supports two modes:
  hold   — activate on key down, deactivate on key up (push-to-talk)
  toggle — tap once to start, tap again to stop

`stop()` unhooks the OS-level listener entirely, so a disabled GPTalks does
no keyboard processing at all (not just ignoring events).

We deliberately use a generic `keyboard.hook()` and filter on the resolved
`event.name` rather than `keyboard.on_press_key(key)`. The `keyboard` library's
scan-code table for "right ctrl" also includes scan code 29 — the same scan
code as plain Left Ctrl — as a workaround for a Windows quirk where Right Ctrl
fires a spurious phantom Left-Ctrl-shaped event alongside the real one. That
makes `on_press_key("right ctrl")` fire on genuine Left Ctrl presses too.
`event.name` doesn't have this problem: real Left Ctrl always resolves to
"ctrl" and real Right Ctrl always resolves to "right ctrl", verified against
Windows' raw low-level keyboard hook.
"""

from __future__ import annotations

from typing import Callable, Optional

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
        self._hook: Optional[object] = None
        self._active = False  # logical state: are we currently dictating?
        self._key_down = False  # physical state: filters Windows key auto-repeat

    @property
    def is_listening(self) -> bool:
        return self._hook is not None

    def start(self) -> None:
        if self._hook is not None:
            return
        self._active = False
        self._key_down = False
        self._hook = keyboard.hook(self._on_event, suppress=False)

    def stop(self) -> None:
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        self._active = False
        self._key_down = False

    def _on_event(self, event) -> None:
        if event.name != self.key:
            return
        if event.event_type == keyboard.KEY_DOWN:
            self._on_press()
        elif event.event_type == keyboard.KEY_UP:
            self._on_release()

    def _on_press(self) -> None:
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

    def _on_release(self) -> None:
        self._key_down = False
        if self.mode == "hold" and self._active:
            self._active = False
            self.on_deactivate()
