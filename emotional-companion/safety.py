import re


HIGH_RISK_PATTERNS = [
    r"\bi want to die\b",
    r"\bwant to kill myself\b",
    r"\bkill myself\b",
    r"\bend my life\b",
    r"\bsuicide\b",
    r"\bsuicidal\b",
    r"\bhurt myself\b",
    r"\bself[- ]harm\b",
    r"\bnot want to live\b",
    r"\bi am going to die\b",
]

MODERATE_RISK_PATTERNS = [
    r"\bi hate myself\b",
    r"\bno reason to live\b",
    r"\bi can't do this anymore\b",
    r"\bi want to disappear\b",
    r"\beveryone would be better without me\b",
]


def detect_risk_level(text: str) -> str:
    text = (text or "").lower().strip()
    if not text:
        return "none"

    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, text):
            return "high"

    for pattern in MODERATE_RISK_PATTERNS:
        if re.search(pattern, text):
            return "moderate"

    return "none"


def build_safety_reply(user_name: str = "there") -> str:
    first_name = (user_name or "there").split()[0]
    return (
        f"{first_name}, I'm really glad you said that out loud.\n"
        "I’m worried about your safety right now.\n"
        "Please reach out to someone near you immediately — a trusted person, local emergency help, or a crisis support line.\n"
        "If you want, stay here and send me one word: 'alone' or 'with someone'."
    )