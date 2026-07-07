"""Configuration loading for GPTalks.

Looks for ``config.yaml`` in the current working directory first, then next to
``main.py`` (the repo root). If neither exists, built-in defaults are used —
these match ``config.example.yaml`` exactly.
"""

from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILENAME = "config.yaml"

# Fillers removed anywhere they appear as a standalone word.
DEFAULT_FILLER_WORDS = ["um", "uh", "er", "ah", "hmm", "mhm"]

# Words that are only sometimes filler ("I like pizza" vs "it was, like, huge").
# These are removed only when set off by commas, so real usage is never touched.
DEFAULT_CAUTIOUS_FILLER_WORDS = ["like", "you know", "i mean"]


@dataclass
class HotkeyConfig:
    key: str = "right ctrl"
    mode: str = "hold"  # "hold" (push-to-talk) or "toggle" (tap start / tap stop)


@dataclass
class WhisperConfig:
    model: str = "base.en"  # "small.en" is the supported quality-up option
    language: str = "en"
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 8


@dataclass
class AudioConfig:
    sample_rate: int = 16000  # Whisper's native rate; avoids a resample pass
    min_duration_sec: float = 0.3
    # Float32 mic samples are in [-1, 1]. A typical quiet-room noise floor sits
    # around 0.001–0.003 RMS while even soft speech exceeds 0.01, so 0.005
    # separates "accidental tap" from "actual speech" with margin on both sides.
    silence_rms_threshold: float = 0.005


@dataclass
class FeedbackConfig:
    beeps: bool = True


@dataclass
class InjectionConfig:
    method: str = "clipboard"  # "clipboard" (paste) or "type" (keystrokes)
    restore_clipboard: bool = True
    # How long to wait after sending Ctrl+V before restoring the clipboard.
    paste_settle_sec: float = 0.3


@dataclass
class CleanupRules:
    strip_fillers: bool = True
    collapse_repeats: bool = True
    trim_whitespace: bool = True
    capitalize_first: bool = True
    ensure_end_punctuation: bool = True


@dataclass
class CleanupConfig:
    enabled: bool = True
    filler_words: List[str] = field(default_factory=lambda: list(DEFAULT_FILLER_WORDS))
    cautious_filler_words: List[str] = field(
        default_factory=lambda: list(DEFAULT_CAUTIOUS_FILLER_WORDS)
    )
    rules: CleanupRules = field(default_factory=CleanupRules)


@dataclass
class AppConfig:
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    injection: InjectionConfig = field(default_factory=InjectionConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    # Resolved path of the loaded config file (None when running on defaults).
    config_path: Optional[Path] = None


def candidate_config_paths() -> List[Path]:
    """Locations searched for config.yaml, in priority order."""
    return [Path.cwd() / CONFIG_FILENAME, APP_ROOT / CONFIG_FILENAME]


def _apply(obj, data: dict) -> None:
    """Recursively overlay a parsed YAML dict onto a dataclass tree."""
    for key, value in data.items():
        name = str(key).strip().lower().replace("-", "_").replace(" ", "_")
        if not hasattr(obj, name):
            print(f"[config] ignoring unknown key: {key}", file=sys.stderr)
            continue
        current = getattr(obj, name)
        if dataclasses.is_dataclass(current) and isinstance(value, dict):
            _apply(current, value)
        elif value is not None:
            setattr(obj, name, value)


def load_config(path: Optional[str] = None) -> AppConfig:
    cfg = AppConfig()
    if path is not None:
        found: Optional[Path] = Path(path)
    else:
        found = next((c for c in candidate_config_paths() if c.exists()), None)
    if found is not None and found.exists():
        # Deferred import: cleanup/config unit tests must not require PyYAML.
        import yaml

        data = yaml.safe_load(found.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            _apply(cfg, data)
        else:
            print(f"[config] {found} is not a mapping; using defaults", file=sys.stderr)
        cfg.config_path = found.resolve()
    return cfg
