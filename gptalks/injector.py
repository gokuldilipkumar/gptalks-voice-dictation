"""Inject text at the cursor of the focused window.

Primary method is clipboard-paste (full Unicode, fast, works in nearly every
app): save the user's clipboard, copy the transcript, send Ctrl+V, then
restore the original clipboard. Falls back to simulated typing if the
clipboard is unavailable.

UIPI caveat: Windows blocks synthesized input from a normal-integrity process
into an elevated (administrator) window. GPTalks itself never needs elevation,
but pasting into an admin Command Prompt/regedit/etc. will silently do nothing
unless GPTalks is also run as administrator. This is OS policy, not a bug here.
"""

from __future__ import annotations

import sys
import time

import keyboard
import pyperclip

from .config import InjectionConfig


class TextInjector:
    def __init__(self, config: InjectionConfig):
        self.config = config

    def inject(self, text: str) -> None:
        if not text:
            return
        if self.config.method == "type":
            self._type(text)
            return
        try:
            self._paste(text)
        except Exception as exc:  # e.g. clipboard locked by another process
            print(f"[injector] paste failed ({exc}); falling back to typing", file=sys.stderr)
            self._type(text)

    def _paste(self, text: str) -> None:
        original = None
        try:
            original = pyperclip.paste()
        except pyperclip.PyperclipException:
            pass  # unreadable clipboard (e.g. holds an image) — skip restore

        pyperclip.copy(text)
        # Brief pause so the clipboard write lands before the paste keystroke.
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        # The focused app reads the clipboard asynchronously after receiving
        # Ctrl+V. Restoring immediately would race it and paste the *old*
        # clipboard contents, so wait for the paste to settle first.
        time.sleep(max(0.0, float(self.config.paste_settle_sec)))
        if self.config.restore_clipboard and original is not None:
            try:
                pyperclip.copy(original)
            except pyperclip.PyperclipException:
                pass

    @staticmethod
    def _type(text: str) -> None:
        # keyboard.write uses unicode key events, so this stays Unicode-safe.
        keyboard.write(text, delay=0.005)
