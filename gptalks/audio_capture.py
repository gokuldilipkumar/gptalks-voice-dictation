"""Microphone capture via sounddevice.

Records mono float32 at 16 kHz (Whisper's native rate) into an in-memory
buffer. Capture is fully callback-driven — no polling loop — and the stream is
closed as soon as recording stops so the mic is released between utterances.
"""

from __future__ import annotations

import threading
from typing import List, Optional

import numpy as np
import sounddevice as sd


class AudioCapture:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._chunks: List[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        # `indata` is reused by PortAudio between callbacks; copy is required.
        with self._lock:
            self._chunks.append(indata.copy())

    def stop(self) -> np.ndarray:
        """Stop recording and return everything captured as a 1-D float32 array."""
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            data = np.concatenate(self._chunks)
            self._chunks = []
        return data[:, 0].copy()

    def duration_sec(self, audio: np.ndarray) -> float:
        return len(audio) / float(self.sample_rate)

    @staticmethod
    def rms(audio: np.ndarray) -> float:
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
