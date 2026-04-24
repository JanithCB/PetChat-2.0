"""
core/esc_support.py -- ESConv-style emotional support planner for PetChat-2.0.

build_esc_support_plan(user_message, history, risk_level, risk_tags)
    -> dict with keys:
        stage           : "exploration" | "comforting" | "action"
        primary_emotion : str
        problem_hint    : str
        strategies      : list[str]
        response_style  : str
        use_emoji       : bool
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Emotion keyword map
# ---------------------------------------------------------------------------

_EMOTION_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(anxious|anxiety|nervous|worried|panic|stress)\b", re.I), "anxiety"),
    (re.compile(r"\b(sad|depress|hopeless|empty|numb|blue)\b", re.I),         "sadness"),
    (re.compile(r"\b(angry|anger|furious|frustrated|mad|irritated)\b", re.I), "anger"),
    (re.compile(r"\b(lonely|alone|isolated|no one|nobody)\b", re.I),          "loneliness"),
    (re.compile(r"\b(guilty|guilt|ashamed|shame|embarrassed)\b", re.I),       "guilt"),
    (re.compile(r"\b(scared|fear|afraid|terrified|phobia)\b", re.I),          "fear"),
    (re.compile(r"\b(grief|griev|loss|lost|miss|mourning)\b", re.I),          "grief"),
    (re.compile(r"\b(overwhelmed|too much|can't cope|exhausted|burnout)\b", re.I), "overwhelm"),
    (re.compile(r"\b(worthless|useless|failure|loser|stupid)\b", re.I),       "low self-worth"),
]

# ---------------------------------------------------------------------------
# Strategy pools per stage
# ---------------------------------------------------------------------------

_STRATEGIES: dict[str, list[str]] = {
    "exploration": [
        "reflective_listening",
        "open_ended_questions",
        "emotional_validation",
    ],
    "comforting": [
        "normalisation",
        "emotional_validation",
        "reframing",
        "affirmation",
    ],
    "action": [
        "psychoeducation",
        "problem_solving",
        "self_care_suggestion",
        "professional_referral",
    ],
}

# ---------------------------------------------------------------------------
# Stage heuristic
# ---------------------------------------------------------------------------

def _infer_stage(history: list[dict[str, str]], risk_level: str) -> str:
    """
    Infer the ESConv support stage from conversation depth and risk.

    exploration  -- first 1-2 turns or low context
    comforting   -- mid conversation or medium risk
    action       -- longer conversation or explicit request for advice
    """
    assistant_turns = sum(1 for m in history if m.get("role") == "assistant")

    if risk_level == "medium" and assistant_turns < 2:
        return "comforting"
    if assistant_turns == 0:
        return "exploration"
    if assistant_turns <= 2:
        return "exploration"
    if assistant_turns <= 5:
        return "comforting"
    return "action"


def _detect_emotion(text: str) -> str:
    for pattern, emotion in _EMOTION_MAP:
        if pattern.search(text):
            return emotion
    return "distress"


def _detect_problem(text: str) -> str:
    """Very lightweight topic hint — helps the LLM ground its reply."""
    topics = {
        "exam|study|assignment|grade|university|school|college": "academic pressure",
        "work|job|boss|colleague|office|career":                 "work stress",
        "friend|friendship|social|group|peer":                   "social relationships",
        "family|parent|sibling|home|household":                  "family conflict",
        "relationship|partner|boyfriend|girlfriend|breakup":     "romantic relationship",
        "money|financial|debt|afford|broke":                     "financial stress",
        "health|sick|illness|pain|hospital":                     "health concerns",
        "sleep|insomnia|tired|exhausted":                        "sleep issues",
    }
    for pattern, label in topics.items():
        if re.search(pattern, text, re.I):
            return label
    return "general emotional distress"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_esc_support_plan(
    user_message: str,
    history: list[dict[str, str]],
    risk_level: str,
    risk_tags: list[str] | None = None,
) -> dict:
    """
    Build an ESConv-style support plan dict.

    Parameters
    ----------
    user_message : Latest user message.
    history      : Conversation history so far.
    risk_level   : "low" | "medium" | "high"
    risk_tags    : Matched risk pattern strings (from safety.py).

    Returns
    -------
    dict with keys: stage, primary_emotion, problem_hint,
                    strategies, response_style, use_emoji
    """
    stage           = _infer_stage(history, risk_level)
    primary_emotion = _detect_emotion(user_message)
    problem_hint    = _detect_problem(user_message)
    strategies      = _STRATEGIES[stage].copy()

    # Tone and emoji rules
    if risk_level == "high":
        response_style = "calm, grounded, direct -- no humour, no emojis"
        use_emoji      = False
    elif risk_level == "medium":
        response_style = "warm, gentle, validating"
        use_emoji      = False
    else:
        response_style = "warm, friendly, conversational"
        use_emoji      = stage != "action"   # no emoji during advice

    return {
        "stage":           stage,
        "primary_emotion": primary_emotion,
        "problem_hint":    problem_hint,
        "strategies":      strategies,
        "response_style":  response_style,
        "use_emoji":       use_emoji,
    }