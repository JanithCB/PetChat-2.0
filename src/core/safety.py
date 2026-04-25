"""
src/core/safety.py -- Offline risk detection and safety replies for PetChat-2.0.

Design principles
-----------------
- Detection is regex + keyword based, fast and fully offline.
- Three levels: "low" | "medium" | "high".
- Tags identify which signals triggered the result.
- No external dependencies.
- Public API:
    detect_risk_level(text) -> tuple[str, list[str]]
    build_safety_reply(risk_level, user_name, tags) -> str
"""

from __future__ import annotations

import re
from typing import NamedTuple


class _Signal(NamedTuple):
    tag: str
    level: str
    patterns: list[re.Pattern[str]]


def _p(*raw: str) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in raw]


_SIGNALS: list[_Signal] = [
    _Signal(
        "suicidal_ideation",
        "high",
        _p(
            r"\bsuicid",
            r"\bkill\s+myself\b",
            r"\bkill\s+my\s*self\b",
            r"\bend\s+(my\s+)?life\b",
            r"\btake\s+my\s+(own\s+)?life\b",
            r"\bwant\s+to\s+die\b",
            r"\bwish\s+i\s+(was|were|am)\s+dead\b",
            r"\bbetter\s+off\s+dead\b",
            r"\bbetter\s+off\s+without\s+me\b",
            r"\bno\s+point\s+in\s+(living|being\s+alive)\b",
            r"\bi\s+don['’]?t\s+want\s+to\s+be\s+here\s+anymore\b",
            r"\bi\s+have\s+nothing\s+to\s+live\s+for\b",
            r"\bplan\s+to\s+(kill|end|hurt)\s+my",
        ),
    ),
    _Signal(
        "self_harm",
        "high",
        _p(
            r"\bself[\s\-]?harm(ing)?\b",
            r"\bhurt(ing)?\s+myself\b",
            r"\bcut(ting)?\s+myself\b",
            r"\bburn(ing)?\s+myself\b",
            r"\bself[\s\-]?injur",
            r"\boverdos(e|ing)\b",
            r"\btook\s+too\s+many\s+(pills|tablets|meds)\b",
        ),
    ),
    _Signal(
        "immediate_danger",
        "high",
        _p(
            r"\bcan['’]?t\s+go\s+on\b",
            r"\bi\s+give\s+up\s+on\s+(life|everything)\b",
            r"\bthere['’]?s\s+no\s+(way\s+out|hope\s+left)\b",
            r"\bi\s+feel\s+like\s+disappearing\s+forever\b",
        ),
    ),
    _Signal(
        "substance_self_harm",
        "high",
        _p(
            r"(drink|drank|drunk|alcohol|pills?|drugs?|meds?).{0,30}(hurt|harm|kill|die|dead|end\s+it)",
            r"(hurt|harm|kill|die|dead|end\s+it).{0,30}(drink|drank|drunk|alcohol|pills?|drugs?|meds?)",
        ),
    ),
    _Signal(
        "hopelessness",
        "medium",
        _p(
            r"\bno\s+hope\b",
            r"\bhopeless(ness)?\b",
            r"\bnothing\s+(will\s+ever\s+)?(get\s+)?(better|change)\b",
            r"\blife\s+is\s+(pointless|meaningless|worthless|not\s+worth\s+it)\b",
            r"\bi\s+feel\s+(so\s+)?empty\b",
            r"\bcompletely\s+numb\b",
            r"\bcan['’]?t\s+see\s+a\s+future\b",
            r"\bwhat['’]?s\s+the\s+point\b",
            r"\btoo\s+tired\s+to\s+(keep\s+)?(going|trying|fighting)\b",
        ),
    ),
    _Signal(
        "emotional_crisis",
        "medium",
        _p(
            r"\bbreaking\s+down\b",
            r"\bcan['’]?t\s+(cope|handle\s+this|take\s+it\s+anymore)\b",
            r"\bfalling\s+apart\b",
            r"\bpanic\s+attack\b",
            r"\blosing\s+my\s+mind\b",
            r"\blosing\s+control\b",
            r"\bfeel(ing)?\s+(so\s+)?alone\b",
            r"\babsolutely\s+desperate\b",
        ),
    ),
    _Signal(
        "self_harm_history",
        "medium",
        _p(
            r"\bused\s+to\s+(cut|hurt|harm)\s+myself\b",
            r"\bi\s+have\s+(cut|hurt|harmed)\s+myself\s+(before|in\s+the\s+past)\b",
            r"\bthoughts?\s+of\s+(hurting|harming|cutting)\s+myself\b",
            r"\burges?\s+to\s+(hurt|harm|cut)\s+myself\b",
        ),
    ),
    _Signal(
        "substance_concern",
        "medium",
        _p(
            r"\bdrinking\s+(too\s+much|every\s+day|to\s+(cope|forget|numb))\b",
            r"\bcan['’]?t\s+stop\s+drinking\b",
            r"\brelapsed?\b",
            r"\busing\s+again\b",
            r"\baddicted\b",
            r"\bdependen(t|cy)\s+on\b",
        ),
    ),
]

_SIGNALS.sort(key=lambda item: 0 if item.level == "high" else 1)


def detect_risk_level(text: str) -> tuple[str, list[str]]:
    """
    Return:
        ("low" | "medium" | "high", tags)
    """
    if not text or not text.strip():
        return "low", []

    fired_high: list[str] = []
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
                break

    if fired_high:
        return "high", fired_high + fired_medium
    if fired_medium:
        return "medium", fired_medium
    return "low", []


def build_safety_reply(
    risk_level: str,
    user_name: str = "",
    tags: list[str] | None = None,
) -> str:
    """
    Plain-text safety reply helper.
    """
    name = (user_name or "").strip()
    tags = tags or []

    if risk_level == "high":
        return _high_risk_reply(name, tags)
    if risk_level == "medium":
        return _medium_risk_reply(name, tags)
    return _low_risk_reply(name)


def _high_risk_reply(user_name: str, tags: list[str]) -> str:
    opener = f"{user_name}, " if user_name else ""

    return (
        f"{opener}what you shared sounds very serious, and your safety matters right now. "
        "Please contact a trusted person, local emergency services, or a crisis support line immediately. "
        "If you are in Sri Lanka, you can contact Sumithrayo on 0800 111 000. "
        "Please do not stay alone if you might act on these thoughts."
    )


def _medium_risk_reply(user_name: str, tags: list[str]) -> str:
    opener = f"{user_name}, " if user_name else ""

    if "hopelessness" in tags:
        middle = (
            "it sounds like things feel very heavy and bleak right now. "
            "You do not have to carry that alone."
        )
    elif "emotional_crisis" in tags:
        middle = (
            "it sounds like things feel overwhelming and hard to hold together right now. "
            "I am taking that seriously."
        )
    elif "self_harm_history" in tags:
        middle = (
            "thank you for saying that out loud. "
            "Those thoughts or urges can feel frightening, and it helps to bring them into words."
        )
    elif "substance_concern" in tags:
        middle = (
            "it sounds like coping has been really hard lately. "
            "That is something worth taking seriously."
        )
    else:
        middle = (
            "what you are sharing sounds really difficult. "
            "I am taking it seriously."
        )

    return (
        f"{opener}{middle} "
        "Please reach out to someone you trust if things get heavier, and seek urgent help immediately if you feel unsafe."
    )


def _low_risk_reply(user_name: str) -> str:
    opener = f"{user_name}, " if user_name else ""
    return f"{opener}I am here and listening."