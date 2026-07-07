"""Unit tests for the rule-based cleanup layer (pytest style, plain asserts).

Run from the repo root:  python -m pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gptalks.cleanup import CleanupEngine
from gptalks.config import CleanupConfig, CleanupRules


def make_engine(enabled=True, **rules_on):
    """Engine with every rule OFF except those passed as keyword args."""
    rules = CleanupRules(
        strip_fillers=False,
        collapse_repeats=False,
        trim_whitespace=False,
        capitalize_first=False,
        ensure_end_punctuation=False,
    )
    for name, value in rules_on.items():
        assert hasattr(rules, name), f"unknown rule: {name}"
        setattr(rules, name, value)
    return CleanupEngine(CleanupConfig(enabled=enabled, rules=rules))


def make_full_engine(enabled=True):
    return CleanupEngine(CleanupConfig(enabled=enabled))


# ---- filler word stripping -------------------------------------------------

def test_strip_filler_at_sentence_start():
    eng = make_engine(strip_fillers=True)
    assert eng.clean("Um, this is a test.") == "this is a test."


def test_strip_filler_mid_sentence_comma_bounded():
    eng = make_engine(strip_fillers=True)
    assert eng.clean("I was, um, thinking about it.") == "I was thinking about it."


def test_strip_filler_before_end_punctuation():
    eng = make_engine(strip_fillers=True)
    assert eng.clean("I already did it, you know.") == "I already did it."


def test_strip_multiple_fillers():
    eng = make_engine(strip_fillers=True)
    assert eng.clean("Uh, so I was, um, walking.") == "so I was walking."


def test_cautious_filler_removed_only_when_comma_bounded():
    eng = make_engine(strip_fillers=True)
    assert eng.clean("It was, like, really far away.") == "It was really far away."
    # "like" as a real verb must never be touched
    assert eng.clean("I like pizza.") == "I like pizza."


def test_filler_not_stripped_inside_words():
    eng = make_engine(strip_fillers=True)
    # "um" inside "circumstance"/"umbrella" must survive
    text = "The circumstance involved an umbrella."
    assert eng.clean(text) == text


def test_filler_free_text_untouched_by_filler_rule():
    eng = make_engine(strip_fillers=True)
    text = "  spacing and Case are not this rule's job  "
    assert eng.clean(text) == text


# ---- repeated-word collapsing ----------------------------------------------

def test_collapse_repeated_words():
    eng = make_engine(collapse_repeats=True)
    assert eng.clean("I I think the the plan works") == "I think the plan works"


def test_collapse_repeats_case_insensitive_keeps_first():
    eng = make_engine(collapse_repeats=True)
    assert eng.clean("The the dog barked") == "The dog barked"


def test_collapse_triple_repeat():
    eng = make_engine(collapse_repeats=True)
    assert eng.clean("go go go now") == "go now"


def test_collapse_handles_contractions():
    eng = make_engine(collapse_repeats=True)
    assert eng.clean("I'm I'm fine") == "I'm fine"


# ---- whitespace trimming -----------------------------------------------------

def test_trim_whitespace():
    eng = make_engine(trim_whitespace=True)
    assert eng.clean("  hello   world  ") == "hello world"


def test_trim_whitespace_only_rule_does_not_capitalize():
    eng = make_engine(trim_whitespace=True)
    assert eng.clean(" hello ") == "hello"


# ---- capitalization ----------------------------------------------------------

def test_capitalize_first_letter():
    eng = make_engine(capitalize_first=True)
    assert eng.clean("hello there.") == "Hello there."


def test_capitalize_never_lowercases():
    eng = make_engine(capitalize_first=True)
    assert eng.clean("HELLO there.") == "HELLO there."


def test_capitalize_skips_leading_number():
    eng = make_engine(capitalize_first=True)
    assert eng.clean("42 things happened.") == "42 things happened."


# ---- end punctuation -----------------------------------------------------------

def test_end_punctuation_added():
    eng = make_engine(ensure_end_punctuation=True)
    assert eng.clean("hello there") == "hello there."


def test_end_punctuation_not_doubled():
    eng = make_engine(ensure_end_punctuation=True)
    assert eng.clean("hello there!") == "hello there!"
    assert eng.clean("really?") == "really?"


# ---- master switch ----------------------------------------------------------

def test_cleanup_disabled_returns_raw_string_unchanged():
    eng = make_full_engine(enabled=False)
    raw = "  um, hello hello world  "
    assert eng.clean(raw) is raw


def test_empty_string_passthrough():
    assert make_full_engine().clean("") == ""


# ---- rule independence ---------------------------------------------------------

def test_rules_are_independent_fillers_only():
    eng = make_engine(strip_fillers=True)
    # no capitalization, no end punctuation added
    assert eng.clean("um, hello world") == "hello world"


def test_rules_are_independent_capitalize_without_fillers():
    eng = make_engine(capitalize_first=True)
    assert eng.clean("um, hello world") == "Um, hello world"


def test_rules_are_independent_repeats_without_trim():
    eng = make_engine(collapse_repeats=True)
    assert eng.clean("wait wait  stop") == "wait  stop"


# ---- full pipeline -----------------------------------------------------------

def test_full_pipeline():
    eng = make_full_engine()
    raw = " um, so I I was, like, thinking about the the plan "
    assert eng.clean(raw) == "So I was thinking about the plan."
