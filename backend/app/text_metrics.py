"""Deterministic transcript metrics.

v1 kept two *different* filler lists (audio vs NLP), counted ordinary words such
as "so"/"like"/"right"/"well" as fillers, and rewarded "confident words" (so
saying "I led, built, managed" raised the score). This module has a single
source of truth and only counts true disfluencies. Ambiguous words ("like",
"so", "well") only count when punctuation/position shows they are used as
fillers.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

WORD_RE = re.compile(r"[A-Za-z0-9']+")

# Unambiguous fillers (matched as whole words / phrases, case-insensitive).
HARD_FILLERS = [
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "or something",
    "or whatever",
    "umm",
    "um",
    "uhh",
    "uh",
    "erm",
    "er",
    "ah",
    "hmm",
    "mmm",
    "basically",
    "literally",
    "honestly",
    "actually",
]
_HARD_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in HARD_FILLERS) + r")\b", re.I)

# "like" is a filler only when set off by punctuation ("it was, like, huge") or doubled.
_LIKE_RE = re.compile(r"(?:(?<=[,.…-])\s*\blike\b\s*(?=[,.…-])|\blike\s+like\b)", re.I)
# "so" / "well" / "okay" as a sentence opener ("So, ...", "Well, ...").
_OPENER_RE = re.compile(r"(?:^|[.!?]\s+)(so|well|okay|ok|right)\s*,", re.I)

HEDGES = [
    "i think",
    "i guess",
    "i suppose",
    "maybe",
    "perhaps",
    "probably",
    "sort of",
    "kind of",
    "somewhat",
    "i feel like",
    "i'm not sure",
    "not sure",
    "i don't know",
]
_HEDGE_RE = re.compile(r"\b(" + "|".join(re.escape(h) for h in HEDGES) + r")\b", re.I)

_REPEAT_RE = re.compile(r"\b(\w{2,})\s+\1\b", re.I)  # "the the", "we we"
_NUMBER_RE = re.compile(r"\b\d[\d,.]*\s?(%|percent|k|m|x|ms|s|users|customers|people|hours|days|weeks|months|years)?\b", re.I)
_IMPACT_RE = re.compile(
    r"\b(increased|reduced|improved|saved|grew|cut|boosted|decreased|launched|delivered|won|"
    r"resulted in|as a result|outcome|impact|achieved|shipped|raised|lowered|doubled|tripled)\b",
    re.I,
)
_ACTION_RE = re.compile(
    r"\b(i (?:built|led|designed|implemented|wrote|created|developed|decided|proposed|fixed|"
    r"organized|organised|managed|drove|analy[sz]ed|owned|learned|taught|negotiated|presented))\b",
    re.I,
)
_CONTEXT_RE = re.compile(r"\b(situation|context|background|challenge|problem|goal|task|at that time|when i was|we were)\b", re.I)


@dataclass
class TextMetrics:
    word_count: int
    filler_count: int
    filler_per_100: float
    fillers: list[tuple[str, int]]
    filler_spans: list[tuple[int, int]]
    hedge_count: int
    repeat_count: int
    unique_ratio: float
    number_count: int
    impact_count: int
    action_count: int
    context_count: int
    first_person_ratio: float | None  # I / (I + we); None if neither used
    extras: dict = field(default_factory=dict)


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def find_fillers(text: str) -> tuple[list[tuple[str, int]], list[tuple[int, int]]]:
    """Returns ([(filler, count)], [(start, end) char spans]) over the original text."""
    spans: list[tuple[int, int, str]] = []
    for m in _HARD_RE.finditer(text):
        spans.append((m.start(), m.end(), m.group(1).lower()))
    for m in _LIKE_RE.finditer(text):
        s = text.lower().find("like", m.start())
        spans.append((s, s + 4, "like"))
    for m in _OPENER_RE.finditer(text):
        spans.append((m.start(1), m.end(1), m.group(1).lower()))
    spans.sort()
    # drop overlaps (e.g. "kind of" inside a longer match)
    merged: list[tuple[int, int, str]] = []
    for s, e, w in spans:
        if merged and s < merged[-1][1]:
            continue
        merged.append((s, e, w))
    counts = Counter(w for _, _, w in merged)
    return counts.most_common(), [(s, e) for s, e, _ in merged]


def analyze_text(text: str) -> TextMetrics:
    text = (text or "").strip()
    words = tokenize(text)
    n = len(words)
    fillers, spans = find_fillers(text)
    filler_count = sum(c for _, c in fillers)

    i_count = sum(1 for w in words if w in {"i", "i'm", "i've", "i'd", "i'll", "my"})
    we_count = sum(1 for w in words if w in {"we", "we're", "we've", "we'd", "we'll", "our", "us"})
    fp = i_count / (i_count + we_count) if (i_count + we_count) else None

    return TextMetrics(
        word_count=n,
        filler_count=filler_count,
        filler_per_100=(filler_count / n * 100) if n else 0.0,
        fillers=fillers,
        filler_spans=spans,
        hedge_count=len(_HEDGE_RE.findall(text)),
        repeat_count=len(_REPEAT_RE.findall(text)),
        unique_ratio=(len(set(words)) / n) if n else 0.0,
        number_count=len(_NUMBER_RE.findall(text)),
        impact_count=len(_IMPACT_RE.findall(text)),
        action_count=len(_ACTION_RE.findall(text)),
        context_count=len(_CONTEXT_RE.findall(text)),
        first_person_ratio=fp,
    )
