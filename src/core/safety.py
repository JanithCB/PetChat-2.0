"""
core/safety.py — Risk detection and safety replies for PetChat-2.0.

Design principles
-----------------
- Detection is keyword + pattern based — fast, offline, no LLM call.
- Three levels: "low" | "medium" | "high".
- Tags identify which signal(s) triggered the level.
- build_safety_reply() returns plain prose only:
    - No emoji, no playful tone, no clinical jargon.
    - No diagnosis, no promise of availability, no claim of being a therapist.
    - High risk: direct encouragement to contact crisis resources.
    - Medium risk: grounded, careful — keep the conversation open.

Public API
----------
detect_risk_level(text)         -> tuple[str, list[str]]
build_safety_reply(risk_level, user_name, tags) -> str
"""

from __future__ import annotations

import re
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

class _Signal(NamedTuple):
    tag:     str
    level:   str                    # "high" | "medium"
    patterns: list[re.Pattern[str]]


def _p(*raw: str) -> list[re.Pattern[str]]:
    """Compile patterns with word-boundary anchors, case-insensitive."""
    return [re.compile(r, re.IGNORECASE) for r in raw]


# Patterns are intentionally broad — false positives are safer than misses.
_SIGNALS: list[_Signal] = [

    # ── HIGH: suicidal ideation ─────────────────────────────────────────
    _Signal("suicidal_ideation", "high", _p(
        r"\bsuicid",                          # suicidal, suicide, suiciding
        r"\bkill\s+my\s*self\b",
        r"\bkill\s+myself\b",
        r"\bend\s+(my\s+)?life\b",
        r"\btake\s+my\s+(own\s+)?life\b",
        r"\bwant\s+to\s+die\b",
        r"\bwish\s+i\s+(was|were|am)\s+dead\b",
        r"\bnot\s+want\s+to\s+(be\s+)?alive\b",
        r"\bbetter\s+off\s+dead\b",
        r"\bbetter\s+off\s+without\s+me\b",
        r"\beveryone\s+would\s+be\s+better\s+off\s+without\s+me\b",
        r"\bno\s+reason\s+to\s+(keep\s+)?live\b",
        r"\bno\s+point\s+in\s+(living|being\s+alive)\b",
        r"\bplan\s+to\s+(kill|end|hurt)\s+my",
        r"\bgoodbye\b.{0,40}\b(forever|for\s+good|everyone)\b",
    )),

    # ── HIGH: self-harm (active) ────────────────────────────────────────
    _Signal("self_harm", "high", _p(
        r"\bcutt?ing\s+(my)?self\b",
        r"\bself[\s\-]?harm(ing)?\b",
        r"\bhurt(ing)?\s+(my)?self\b",
        r"\bburn(ing)?\s+(my)?self\b",
        r"\bself[\s\-]?injur",
        r"\bstarv(ing|e)\s+(my)?self\b",
        r"\boverdo(se|sing)\b",
        r"\btook\s+too\s+many\s+(pills|tablets|meds)\b",
    )),

    # ── HIGH: immediate danger / crisis ────────────────────────────────
    _Signal("immediate_danger", "high", _p(
        r"\bcan\'?t\s+(go\s+on|do\s+this\s+anymore)\b",
        r"\bi\s+give\s+up\s+on\s+(life|everything)\b",
        r"\bthere\'?s\s+no\s+(way\s+out|hope\s+left)\b",
        r"\bi\s+have\s+nothing\s+to\s+live\s+for\b",
        r"\bi\s+feel\s+like\s+disappearing\s+forever\b",
        r"\bi\s+don\'?t\s+want\s+to\s+be\s+here\s+(anymore|any\s+more)\b",
    )),

    # ── HIGH: substance + self-harm combo ──────────────────────────────
    _Signal("substance_self_harm", "high", _p(
        r"(drank?|drank|drink|drunk|pills?|drugs?|alcohol|meds?).{0,30}(hurt|harm|kill|die|dead|end\s+it)",
        r"(hurt|harm|kill|die|dead|end\s+it).{0,30}(drank?|drink|drunk|pills?|drugs?|alcohol|meds?)",
    )),

    # ── MEDIUM: hopelessness / passive ideation ─────────────────────────
    _Signal("hopelessness", "medium", _p(
        r"\bno\s+hope\b",
        r"\bhopeless(ness)?\b",
        r"\bnothing\s+(will\s+ever\s+)?(get\s+)?(better|change)\b",
        r"\blife\s+is\s+(pointless|meaningless|worthless|not\s+worth\s+it)\b",
        r"\bi\s+feel\s+(so\s+)?empty\s+(inside)?\b",
        r"\bcompletely\s+numb\b",
        r"\bcan\'?t\s+see\s+a\s+future\b",
        r"\bno\s+future\s+for\s+me\b",
        r"\bwhat\'?s\s+the\s+point\b",
        r"\bgive\s+up\b",
        r"\btoo\s+tired\s+to\s+(keep\s+)?(going|trying|fighting)\b",
    )),

    # ── MEDIUM: emotional crisis (not yet at high risk) ─────────────────
    _Signal("emotional_crisis", "medium", _p(
        r"\bbreaking\s+down\b",
        r"\bcan\'?t\s+(cope|handle\s+this|take\s+it\s+anymore)\b",
        r"\bfalling\s+apart\b",
        r"\bfeel(ing)?\s+(so\s+)?(alone|completely\s+alone|utterly\s+alone)\b",
        r"\babsolutely\s+desperate\b",
        r"\bpanic\s+attack\b",
        r"\blose\s+my\s+mind\b",
        r"\blosing\s+my\s+mind\b",
        r"\blosing\s+control\b",
    )),

    # ── MEDIUM: self-harm (past / passive mention) ───────────────────────
    _Signal("self_harm_history", "medium", _p(
        r"\bused\s+to\s+(cut|hurt|harm)\s+(my)?self\b",
        r"\bi\s+have\s+(cut|hurt|harmed)\s+(my)?self\s+(before|in\s+the\s+past)\b",
        r"\bthoughts?\s+of\s+(hurting|harming|cutting)\s+(my)?self\b",
        r"\burge(s)?\s+to\s+(hurt|harm|cut)\s+(my)?self\b",
    )),

    # ── MEDIUM: substance abuse concern ─────────────────────────────────
    _Signal("substance_concern", "medium", _p(
        r"\bdrinking\s+(too\s+much|every\s+day|to\s+(cope|forget|numb))\b",
        r"\bcan\'?t\s+stop\s+drinking\b",
        r"\brelapsed?\b",
        r"\busing\s+again\b",
        r"\baddicted\b",
        r"\bdependen(t|cy)\s+on\b",
    )),
]

# Pre-sort: high before medium so the first match at the highest level wins.
_SIGNALS.sort(key=lambda s: 0 if s.level == "high" else 1)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_risk_level(text: str) -> tuple[str, list[str]]:
    """
    Scan text for risk signals.

    Returns
    -------
    (risk_level, tags)
        risk_level : "low" | "medium" | "high"
        tags       : list of signal tag strings that fired (may be empty)

    The function is deterministic and has no side effects — safe to call
    multiple times and easy to unit-test.
    """
    if not text or not text.strip():
        return "low", []

    fired_high:   list[str] = []
    fired_medium: list[str] = []

    for signal in _SIGNALS:
        for pattern in signal.patterns:
            if pattern.search(text):
                if signal.level == "high":
                    if signal.tag not in fired_high:
                        fired_high.append(signal.tag)
                else:
                    if signal.tag not in fired_medium:
                        fired_medium.append(signal.tag)
                break  # one match per signal is enough

    if fired_high:
        return "high", fired_high + fired_medium
    if fired_medium:
        return "medium", fired_medium
    return "low", []


# ---------------------------------------------------------------------------
# Safety replies
# ---------------------------------------------------------------------------

# Crisis hotlines referenced in replies — intentionally minimal and global-first.
_HOTLINES = (
    "988 (Suicide & Crisis Lifeline — US, call or text)",
    "116 123 (Samaritans — UK/Ireland)",
    "13 11 14 (Lifeline — Australia)",
    "iCall: 9152987821 (India)",
)

_HOTLINE_BLOCK = "\n".join(f"  - {h}" for h in _HOTLINES)


def build_safety_reply(
    risk_level: str,
    user_name: str = "there",
    tags: list[str] | None = None,
) -> str:
    """
    Return a plain-prose safety reply appropriate for the given risk level.

    Parameters
    ----------
    risk_level : "high" | "medium" | "low"
    user_name  : The user's first name or "there" if unknown.
    tags       : Signal tags from detect_risk_level (used for fine-tuning wording).

    Rules enforced here
    -------------------
    - No emoji.
    - No playful tone, no casual slang.
    - No diagnosis, no promise of always being available.
    - No claim of being a therapist or counsellor.
    - Warm but grounded.
    """
    tags = tags or []
    name = user_name.strip() or "there"

    if risk_level == "high":
        return _high_risk_reply(name, tags)
    if risk_level == "medium":
        return _medium_risk_reply(name, tags)
    # "low" should not normally reach this function, but handle gracefully.
    return _low_risk_holding_reply(name)


def _high_risk_reply(name: str, tags: list[str]) -> str:
    opener = (
        f"Hey {name}, I hear you, and I'm really glad you said something."
        if name != "there"
        else "I hear you, and I'm really glad you said something."
    )
    return (
        f"{opener}\n\n"
        "What you're feeling right now sounds incredibly heavy, "
        "and you don't have to carry it alone.\n\n"
        "Please reach out to a crisis line right now — "
        "trained people are available 24/7 and they want to help:\n"
        f"{_HOTLINE_BLOCK}\n\n"
        "If you are in immediate danger, please call your local emergency number.\n\n"
        "I'm here with you in this moment."
    )


def _medium_risk_reply(name: str, tags: list[str]) -> str:
    opener = f"I'm with you, {name}." if name != "there" else "I'm with you."

    if "hopelessness" in tags:
        middle = (
            "When everything feels pointless and nothing seems to help, "
            "that kind of pain can be overwhelming. "
            "I want to understand more about what you're going through."
        )
    elif "emotional_crisis" in tags:
        middle = (
            "It sounds like things feel really out of control right now. "
            "That's an incredibly hard place to be. "
            "I'm listening, and I'm not going anywhere."
        )
    elif "self_harm_history" in tags:
        middle = (
            "Thank you for trusting me with that. "
            "Those urges can be really frightening, and it takes courage to talk about them. "
            "Can you tell me a bit more about what's been happening for you lately?"
        )
    elif "substance_concern" in tags:
        middle = (
            "It sounds like things have been really difficult and you've been finding it hard to cope. "
            "That's worth talking about properly, with someone who can really support you."
        )
    else:
        middle = (
            "What you're sharing sounds really hard, "
            "and I want you to know I'm taking it seriously. "
            "You don't have to work through this on your own."
        )

    return (
        f"{opener} {middle}\n\n"
        "If at any point things feel too heavy to bear, "
        "please talk to someone you trust, or reach out to a support line:\n"
        f"{_HOTLINE_BLOCK}"
    )


def _low_risk_holding_reply(name: str) -> str:
    """Fallback — should not normally be called at low risk."""
    opener = f"I'm here, {name}." if name != "there" else "I'm here."
    return f"{opener} Take your time — I'm listening."
