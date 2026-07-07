"""Rule-based transcript tidy-up.

Pure regex passes over a short string — no LLM, no network, runs in well under
a millisecond. faster-whisper already emits punctuation and casing, so this is
a light polish: strip disfluencies, collapse stutters, fix whitespace and
sentence boundaries. It never rewrites or invents words; when a pattern is
ambiguous the text is left alone.
"""

from __future__ import annotations

import re
from typing import List, Pattern, Tuple

from .config import CleanupConfig

_Sub = Tuple[Pattern[str], str]


def _word_regex(word: str) -> str:
    # Multi-word fillers ("you know") should match across any whitespace.
    return r"\s+".join(re.escape(part) for part in word.split())


def _patterns_for(word: str, cautious: bool) -> List[_Sub]:
    esc = _word_regex(word)
    pats: List[_Sub] = [
        # Comma-bounded: "I was, um, thinking" -> "I was thinking".
        # Both commas exist only because of the filler, so both are dropped.
        (re.compile(rf"(?i),\s*{esc}\s*,\s*"), " "),
        # Before sentence-final punctuation: "I did it, you know." -> "I did it."
        (re.compile(rf"(?i),\s*{esc}\s*(?=[.!?])"), ""),
    ]
    if not cautious:
        # Standalone occurrence anywhere. The hyphen in the lookarounds keeps
        # compounds like "uh-huh" intact.
        pats.append((re.compile(rf"(?i)(?<![\w'\-]){esc}(?![\w'\-])[,.]?\s*"), ""))
    return pats


class CleanupEngine:
    _REPEAT_RE = re.compile(r"(?i)\b([\w']+)(?:\s+\1)+\b")

    def __init__(self, config: CleanupConfig):
        self.config = config
        self._filler_subs: List[_Sub] = []
        for word in config.filler_words:
            self._filler_subs.extend(_patterns_for(word, cautious=False))
        for word in config.cautious_filler_words:
            self._filler_subs.extend(_patterns_for(word, cautious=True))

    def clean(self, text: str) -> str:
        if not self.config.enabled or not text:
            return text
        rules = self.config.rules
        if rules.strip_fillers:
            text = self._strip_fillers(text)
        if rules.collapse_repeats:
            text = self._REPEAT_RE.sub(r"\1", text)
        if rules.trim_whitespace:
            text = re.sub(r"\s+", " ", text).strip()
        if rules.capitalize_first:
            text = self._capitalize_first(text)
        if rules.ensure_end_punctuation:
            text = self._ensure_end_punctuation(text)
        return text

    def _strip_fillers(self, text: str) -> str:
        out = text
        for pattern, repl in self._filler_subs:
            out = pattern.sub(repl, out)
        # Only repair if something was removed, so this rule has no effect on
        # filler-free text (keeps rule toggles independent).
        if out != text:
            out = self._repair(out)
        return out

    @staticmethod
    def _repair(text: str) -> str:
        """Fix punctuation/spacing artifacts left behind by filler removal."""
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)  # "word ," -> "word,"
        text = re.sub(r",(?=[,.!?;:])", "", text)  # ",." -> "."
        text = re.sub(r"^[\s,.;:!?]+", "", text)  # orphaned leading punctuation
        text = re.sub(r"[\s,;:]+$", "", text)  # dangling trailing comma
        return text

    @staticmethod
    def _capitalize_first(text: str) -> str:
        for i, ch in enumerate(text):
            if ch.isalpha():
                return text[:i] + ch.upper() + text[i + 1 :]
            if ch.isdigit():
                # Sentences may legitimately start with a number; the first
                # letter after it is mid-sentence and must not be touched.
                return text
        return text

    @staticmethod
    def _ensure_end_punctuation(text: str) -> str:
        if text and text[-1].isalnum():
            return text + "."
        return text
