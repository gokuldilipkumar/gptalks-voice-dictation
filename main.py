"""GPTalks entry point.

Wires together: hotkey -> mic capture -> (worker thread) transcribe -> cleanup
-> paste. The Whisper model loads once here at startup; transcription runs on
a dedicated worker thread fed by a queue so the hotkey hooks and tray UI never
block.

Run with:  python main.py
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading
import time

import numpy as np

from gptalks.audio_capture import AudioCapture
from gptalks.cleanup import CleanupEngine
from gptalks.config import APP_ROOT, CONFIG_FILENAME, load_config
from gptalks.hotkey_listener import HotkeyListener
from gptalks.injector import TextInjector
from gptalks.transcriber import Transcriber
from gptalks.tray_app import State, TrayApp

try:
    import winsound
except ImportError:  # non-Windows: beeps become no-ops, everything else works
    winsound = None


class GPTalksApp:
    def __init__(self):
        self.config = load_config()
        source = self.config.config_path or "built-in defaults"
        print(f"[gptalks] config: {source}")

        print(f"[gptalks] loading Whisper model '{self.config.whisper.model}' "
              f"({self.config.whisper.device}/{self.config.whisper.compute_type}, "
              f"{self.config.whisper.cpu_threads} threads)...")
        t0 = time.perf_counter()
        self.transcriber = Transcriber(self.config.whisper)
        print(f"[gptalks] model ready in {time.perf_counter() - t0:.1f}s")

        self.audio = AudioCapture(sample_rate=self.config.audio.sample_rate)
        self.cleanup = CleanupEngine(self.config.cleanup)
        self.injector = TextInjector(self.config.injection)

        self.enabled = True
        self._recording = False

        self._jobs: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        self.hotkey = HotkeyListener(
            key=self.config.hotkey.key,
            mode=self.config.hotkey.mode,
            on_activate=self._on_record_start,
            on_deactivate=self._on_record_stop,
        )
        self.tray = TrayApp(
            is_enabled=lambda: self.enabled,
            on_toggle_enabled=self._toggle_enabled,
            is_cleanup_on=lambda: self.config.cleanup.enabled,
            on_toggle_cleanup=self._toggle_cleanup,
            on_open_settings=self._open_settings,
            on_quit=self._quit,
        )

    def run(self) -> None:
        self.hotkey.start()
        mode = "hold" if self.config.hotkey.mode == "hold" else "tap to start/stop"
        print(f"[gptalks] ready — {mode} '{self.config.hotkey.key}' to dictate")
        self.tray.run()  # blocks on the main thread until Quit

    # ---- recording -----------------------------------------------------

    def _on_record_start(self) -> None:
        if self._recording:
            return
        try:
            self.audio.start()
        except Exception as exc:
            print(f"[gptalks] could not open microphone: {exc}", file=sys.stderr)
            return
        self._recording = True
        self.tray.set_state(State.RECORDING)
        self._beep(880, 90)

    def _on_record_stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        audio = self.audio.stop()
        self._beep(520, 90)

        duration = self.audio.duration_sec(audio)
        if duration < self.config.audio.min_duration_sec:
            # Accidental tap — not enough audio to contain a word.
            self.tray.set_state(State.IDLE)
            return
        if AudioCapture.rms(audio) < self.config.audio.silence_rms_threshold:
            # Near-silent: mic was open but nobody spoke; skip to avoid
            # Whisper hallucinating text from noise.
            self.tray.set_state(State.IDLE)
            return

        self.tray.set_state(State.TRANSCRIBING)
        self._jobs.put(audio)

    # ---- worker thread -------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            audio = self._jobs.get()
            if audio is None:
                return
            try:
                raw = self.transcriber.transcribe(audio)
                text = self.cleanup.clean(raw)
                if text:
                    self.injector.inject(text)
                else:
                    print("[gptalks] nothing transcribed")
            except Exception as exc:
                print(f"[gptalks] transcription failed: {exc}", file=sys.stderr)
            finally:
                if not self._recording:
                    self.tray.set_state(State.IDLE)

    # ---- tray callbacks ------------------------------------------------

    def _toggle_enabled(self) -> None:
        self.enabled = not self.enabled
        if self.enabled:
            self.hotkey.start()
            print("[gptalks] enabled")
        else:
            self.hotkey.stop()
            if self._recording:
                # Disabled mid-recording: release the mic and discard audio.
                self._recording = False
                self.audio.stop()
            self.tray.set_state(State.IDLE)
            print("[gptalks] disabled")

    def _toggle_cleanup(self) -> None:
        self.config.cleanup.enabled = not self.config.cleanup.enabled
        state = "on" if self.config.cleanup.enabled else "off"
        print(f"[gptalks] cleanup {state}")

    def _open_settings(self) -> None:
        path = self.config.config_path
        if path is None:
            path = APP_ROOT / CONFIG_FILENAME
            example = APP_ROOT / "config.example.yaml"
            if not path.exists() and example.exists():
                shutil.copyfile(example, path)
        try:
            import os

            os.startfile(path)  # opens in the default .yaml editor
        except (AttributeError, OSError):
            subprocess.Popen(["notepad", str(path)])

    def _quit(self) -> None:
        self.hotkey.stop()
        if self._recording:
            self._recording = False
            self.audio.stop()
        self._jobs.put(None)
        self.tray.stop()

    # ---- feedback --------------------------------------------------------

    def _beep(self, freq_hz: int, duration_ms: int) -> None:
        if not self.config.feedback.beeps or winsound is None:
            return
        # winsound.Beep blocks for the beep's duration; keep it off the
        # hotkey callback thread.
        threading.Thread(
            target=winsound.Beep, args=(freq_hz, duration_ms), daemon=True
        ).start()


def main() -> None:
    app = GPTalksApp()
    app.run()


if __name__ == "__main__":
    main()
