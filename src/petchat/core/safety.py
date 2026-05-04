"""
core/safety.py -- Risk detection for PetChat-2.0.

detect_risk_level(text) -> tuple[str, list[str]]
    Returns (risk_level, matched_tags) where risk_level is one of:
        "high"   -- immediate crisis / self-harm / suicidal ideation
        "medium" -- significant distress, burnout, hopelessness
        "low"    -- everyday emotional support
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

_HIGH_PATTERNS: list[str] = [
    r"\bkill (myself|me)\b",
    r"\bsuicid\w*\b",
    r"\bwant to die\b",
    r"\bend (my|this) life\b",
    r"\bself[- ]?harm\b",
    r"\bcut (myself|my wrists)\b",
    r"\bno reason to live\b",
    r"\bcan't go on\b",
    r"\bdon't want to (be here|exist|live)\b",
    r"\boverdose\b",
    r"\bhang (myself|me)\b",
    r"\bjump (off|from)\b",
    r"\bplan to (die|end it)\b",
    r"\bgoodbye (forever|everyone|world)\b",
]

_MEDIUM_PATTERNS: list[str] = [
    r"\bcan't cope\b",
    r"\bfalling apart\b",
    r"\bgive up\b",
    r"\bno hope\b",
    r"\bhopeless\b",
    r"\bworthless\b",
    r"\bburnt? ?out\b",
    r"\bbreakdown\b",
    r"\bpanic attack\b",
    r"\bcan't sleep\b",
    r"\bnumb\b",
    r"\bdepressed\b",
    r"\banxious all the time\b",
    r"\boverwhelmed\b",
    r"\bshaking\b",
    r"\bscared all the time\b",
]

_HIGH_RE:   list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _HIGH_PATTERNS]
_MEDIUM_RE: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in _MEDIUM_PATTERNS]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_risk_level(text: str) -> tuple[str, list[str]]:
    """
    Scan text for risk indicators.

    Returns
    -------
    (risk_level, matched_tags)
        risk_level  : "high" | "medium" | "low"
        matched_tags: list of pattern strings that fired
    """
    matched: list[str] = []

    for pat in _HIGH_RE:
        if pat.search(text):
            matched.append(pat.pattern)

    if matched:
        return "high", matched

    for pat in _MEDIUM_RE:
        if pat.search(text):
            matched.append(pat.pattern)

    if matched:
        return "medium", matched

    return "low", []


def is_high_risk(text: str) -> bool:
    level, _ = detect_risk_level(text)
    return level == "high"