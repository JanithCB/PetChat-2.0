import re
from typing import List, Tuple


HIGH_RISK_PATTERNS = [
    r"\bi want to die\b",
    r"\bi wanna die\b",
    r"\bwant to kill myself\b",
    r"\bkill myself\b",
    r"\bend my life\b",
    r"\bend it all\b",
    r"\bsuicide\b",
    r"\bsuicidal\b",
    r"\bhurt myself\b",
    r"\bself[- ]harm\b",
    r"\bnot want to live\b",
    r"\bi do not want to live\b",
    r"\bi don't want to live\b",
    r"\bi don't want to live anymore\b",
    r"\bi do not want to live anymore\b",
    r"\bbetter off dead\b",
    r"\btake my own life\b",
    r"\bi am going to die\b",
    r"\bi am going to kill myself\b",
    r"\bi'm going to kill myself\b",
    r"\bi might kill myself\b",
    r"\bi should kill myself\b",
]

MEDIUM_RISK_PATTERNS = [
    r"\bi hate myself\b",
    r"\bno reason to live\b",
    r"\bi can't do this anymore\b",
    r"\bi cant do this anymore\b",
    r"\bi want to disappear\b",
    r"\bi wish i could disappear\b",
    r"\beveryone would be better without me\b",
    r"\beverything is pointless\b",
    r"\beverything feels pointless\b",
    r"\beverything seems pointless\b",
    r"\beverything looks pointless\b",
    r"\bfeels pointless\b",
    r"\bseems pointless\b",
    r"\blooks pointless\b",
    r"\bwhat is the point of living\b",
    r"\bwhat's the point of living\b",
    r"\bnothing feels worth it\b",
    r"\bnothing seems worth it\b",
    r"\bi feel hopeless\b",
    r"\bi am hopeless\b",
    r"\bi'm hopeless\b",
    r"\bi give up\b",
    r"\bnobody cares about me\b",
    r"\bi feel empty\b",
    r"\bi feel numb\b",
]

LOW_RISK_HINTS = [
    "lonely",
    "alone",
    "ignored",
    "heartbroken",
    "rejected",
    "sad",
    "overwhelmed",
    "stressed",
    "anxious",
    "upset",
    "hurt",
    "crying",
]


def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def detect_risk_level(text: str) -> Tuple[str, List[str]]:
    text = _normalize_text(text)
    tags: List[str] = []

    if not text:
        return "low", tags

    if _matches_any(text, HIGH_RISK_PATTERNS):
        tags.append("suicidal")
        if "alone" in text or "no one" in text or "by myself" in text:
            tags.append("isolation")
        return "high", tags

    if _matches_any(text, MEDIUM_RISK_PATTERNS):
        if re.search(r"\bhate myself\b", text):
            tags.append("self_loathing")
        if re.search(r"\bhopeless\b|\bpointless\b|\bno reason to live\b|\bgive up\b|\bworth it\b", text):
            tags.append("hopelessness")
        if "alone" in text or "lonely" in text or "no one" in text:
            tags.append("isolation")
        return "medium", tags

    if any(hint in text for hint in LOW_RISK_HINTS):
        tags.append("distress")
        return "low", tags

    return "low", tags


def build_safety_reply(
    risk_level: str,
    user_name: str = "there",
    tags: List[str] | None = None,
) -> str:
    tags = tags or []
    first_name = (user_name or "there").split()[0]

    if risk_level == "high":
        return (
            f"{first_name}, I'm really glad you said that out loud.\n"
            "I'm worried about your safety right now.\n"
            "If you might act on this tonight, call local emergency services or a crisis line right now, "
            "or go to a trusted person near you and stay with them.\n"
            "Can you call or message one trusted person right now and tell them you need them with you?"
        )

    if risk_level == "medium":
        return (
            f"{first_name}, that sounds really heavy.\n"
            "I'm glad you said it instead of holding it in by yourself.\n"
            "What hit you the hardest today?"
        )

    return (
        f"{first_name}, that sounds really painful.\n"
        "I'm here with you.\n"
        "Do you want to tell me what happened?"
    )