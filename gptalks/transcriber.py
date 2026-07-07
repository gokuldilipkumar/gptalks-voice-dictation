"""Local speech-to-text via faster-whisper (CPU, int8)."""

from __future__ import annotations

from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from .config import WhisperConfig


class Transcriber:
    """Wraps a faster-whisper model. Construct once at startup — model load
    takes seconds; transcription of a short utterance takes well under that."""

    def __init__(self, config: WhisperConfig):
        self.config = config
        self.model = WhisperModel(
            config.model,
            device=config.device,
            compute_type=config.compute_type,
            cpu_threads=int(config.cpu_threads),
        )
        self._language = self._resolve_language(config)

    @staticmethod
    def _resolve_language(config: WhisperConfig) -> Optional[str]:
        if config.model.endswith(".en"):
            return "en"  # English-only models reject other language codes
        lang = (config.language or "").strip().lower()
        if lang in ("", "auto", "none"):
            return None  # let Whisper auto-detect
        return lang

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _info = self.model.transcribe(
            audio,
            language=self._language,
            beam_size=5,
            vad_filter=True,  # trims silence and suppresses hallucinated text
        )
        # `segments` is a lazy generator; joining it here runs the actual decode.
        return " ".join(seg.text.strip() for seg in segments).strip()
