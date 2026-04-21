from __future__ import annotations

import random
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple


SAFE_STRATEGIES = (
    "Question",
    "Restatement or Paraphrasing",
    "Reflection of Feelings",
    "Affirmation and Reassurance",
    "Providing Suggestions",
    "Information",
    "Others",
)


HEAVY_EMOTIONS = {
    "grief",
    "shame",
    "fear",
}


EMOTION_PATTERNS: Dict[str, List[str]] = {
    "grief": [
        r"\bbroke up\b",
        r"\bbreakup\b",
        r"\bheartbroken\b",
        r"\bmy heart is broken\b",
        r"\bheart is broken\b",
        r"\bheart\b.{0,10}\bbroken\b",
        r"\bheart\b.{0,10}\bbreaking\b",
        r"\bmiss(?:ing)? (him|her|them)\b",
        r"\blost someone\b",
        r"\bgrief\b",
        r"\bgrieving\b",
        r"\bfuneral\b",
        r"\bignored me\b",
        r"\brejected\b",
        r"\bgot rejected\b",
        r"\bcrush\b",
        r"\bproposed\b",
        r"\bhe left me\b",
        r"\bshe left me\b",
        r"\bthey left me\b",
        r"\bended things\b",
        r"\bgirlfriend left\b",
        r"\bboyfriend left\b",
        r"\bpartner left\b",
        r"\bleft me\b",
        r"\bcan't stop thinking about\b",
        r"\bcannot stop thinking about\b",
    ],
    "lonely": [
        r"\blonely\b",
        r"\balone\b",
        r"\bisolated\b",
        r"\bno one\b",
        r"\bby myself\b",
        r"\bnobody cares\b",
        r"\bnobody wants me\b",
        r"\bno friends\b",
    ],
    "anxiety": [
        r"\banxious\b",
        r"\banxiety\b",
        r"\bpanic\b",
        r"\boverwhelm(?:ed|ing)?\b",
        r"\bcan't calm down\b",
        r"\bcannot calm down\b",
        r"\bworried\b",
        r"\bstressed\b",
        r"\btense\b",
        r"\bracing thoughts\b",
        r"\bmy mind won't stop\b",
        r"\bmy heart is racing\b",
    ],
    "sadness": [
        r"\bsad\b",
        r"\bempty\b",
        r"\bdown\b",
        r"\bdepressed\b",
        r"\bhurt\b",
        r"\bcry(?:ing)?\b",
        r"\bexhausted\b",
        r"\bnumb\b",
        r"\blow\b",
        r"\bheavy\b",
        r"\bhorrible\b",
        r"\bterrible\b",
        r"\bawful\b",
        r"\bmiserable\b",
    ],
    "shame": [
        r"\bashamed\b",
        r"\bembarrassed\b",
        r"\bi hate myself\b",
        r"\bworthless\b",
        r"\bfailure\b",
        r"\bdisgusted with myself\b",
        r"\bi'm the problem\b",
        r"\bi am the problem\b",
    ],
    "anger": [
        r"\bangry\b",
        r"\bmad\b",
        r"\bfurious\b",
        r"\bfrustrated\b",
        r"\birritated\b",
        r"\bpissed\b",
        r"\bannoyed\b",
    ],
    "fear": [
        r"\bafraid\b",
        r"\bscared\b",
        r"\bterrified\b",
        r"\bfear\b",
    ],
    "disgust": [
        r"\bdisgusted\b",
        r"\brepulsed\b",
        r"\bsick of\b",
    ],
}


INTENSITY_PATTERNS: Dict[int, List[str]] = {
    5: [
        r"\bcan't do this\b",
        r"\bcannot do this\b",
        r"\bfalling apart\b",
        r"\bbreaking down\b",
        r"\bi can't cope\b",
        r"\bi cannot cope\b",
        r"\bi'm done\b",
        r"\bi am done\b",
    ],
    4: [
        r"\bextremely\b",
        r"\bcompletely\b",
        r"\bterribly\b",
        r"\bdeeply\b",
        r"\bso much\b",
        r"\bheartbroken\b",
        r"\bdevastated\b",
    ],
    3: [
        r"\breally\b",
        r"\bvery\b",
        r"\bquite\b",
        r"\bhard\b",
        r"\bheavy\b",
        r"\brough\b",
    ],
}


ADVICE_PATTERNS = [
    r"\bwhat should i do\b",
    r"\bwhat do i do\b",
    r"\bhow do i\b",
    r"\bshould i\b",
    r"\bany advice\b",
    r"\bhelp me\b",
    r"\bhow can i\b",
    r"\bwhat can i do\b",
]


DETAIL_PATTERNS = [
    r"\bbecause\b",
    r"\bsince\b",
    r"\bafter\b",
    r"\bwhen\b",
    r"\bit happened\b",
    r"\bhe said\b",
    r"\bshe said\b",
    r"\bthey said\b",
    r"\bdue to\b",
    r"\blast week\b",
    r"\byesterday\b",
    r"\blast night\b",
    r"\blast month\b",
]


QUESTION_PATTERNS = [
    r"\?",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\bdo you think\b",
]


ACTION_READINESS_PATTERNS = [
    r"\bi just need\b",
    r"\bi need a way\b",
    r"\bi want to feel better\b",
    r"\bhow can i get through\b",
    r"\bwhat can help\b",
    r"\bhow do i move on\b",
]


VALIDATION_NEED_PATTERNS = [
    r"\bi feel\b",
    r"\bit hurts\b",
    r"\bthis hurts\b",
    r"\bi'm tired\b",
    r"\bi am tired\b",
    r"\bi can't stop\b",
    r"\bi cannot stop\b",
    r"\bit feels\b",
]


POST_CRISIS_PATTERNS = [
    r"\bwon't do anything\b",
    r"\bwill not do anything\b",
    r"\bi'm safe\b",
    r"\bi am safe\b",
    r"\bbut i still feel\b",
    r"\bstill feel\b",
    r"\bstill hurt\b",
    r"\bstill horrible\b",
    r"\bstill terrible\b",
    r"\bnot going to hurt\b",
]


SHORT_DISTRESS_SIGNALS = {
    "help",
    "i'm not okay",
    "im not okay",
    "i feel bad",
    "i feel horrible",
    "not okay",
}


COMFORT_OVERRIDE_PHRASES = [
    r"\bhorrible\b",
    r"\bterrible\b",
    r"\bawful\b",
    r"\bmiserable\b",
    r"\bnot okay\b",
    r"\bcan't calm\b",
    r"\bcannot calm\b",
    r"\boverwhelm\b",
    r"\bcan't stop\b",
    r"\bcannot stop\b",
]


PROBLEM_HINTS = {
    "romantic_rejection": [
        r"\bcrush\b",
        r"\bproposed\b",
        r"\bignored me\b",
        r"\brejected\b",
        r"\bdoesn't like me\b",
        r"\bdoes not like me\b",
        r"\bghosted\b",
    ],
    "relationship": [
        r"\bbroke up\b",
        r"\bpartner\b",
        r"\bboyfriend\b",
        r"\bgirlfriend\b",
        r"\bex\b",
        r"\bmarriage\b",
        r"\bleft me\b",
        r"\bended things\b",
    ],
    "friendship": [
        r"\bfriend\b",
        r"\bfriends\b",
    ],
    "family": [
        r"\bmother\b",
        r"\bfather\b",
        r"\bparents\b",
        r"\bfamily\b",
        r"\bsister\b",
        r"\bbrother\b",
    ],
    "work": [
        r"\bjob\b",
        r"\bwork\b",
        r"\boffice\b",
        r"\bboss\b",
        r"\bcoworker\b",
    ],
    "academic": [
        r"\bexam\b",
        r"\bschool\b",
        r"\bcollege\b",
        r"\buniversity\b",
        r"\bclass\b",
        r"\bassignment\b",
        r"\bstudy\b",
    ],
    "health": [
        r"\bhealth\b",
        r"\bsick\b",
        r"\bdiagnosis\b",
        r"\binsomnia\b",
        r"\bsleep\b",
    ],
    "self-worth": [
        r"\bworthless\b",
        r"\bfailure\b",
        r"\bhate myself\b",
        r"\bnot enough\b",
    ],
}


ALWAYS_COMFORT_EMOTIONS = {"grief", "lonely", "sadness", "fear", "shame"}


_EMOJI_BY_EMOTION = {
    ("sadness", "light"): ["😔", "🥺", "🤍"],
    ("sadness", "medium"): ["😔", "😞"],
    ("lonely", "light"): ["🥺", "🤍", "💙"],
    ("lonely", "medium"): ["😔", "🤍"],
    ("anxiety", "light"): ["💛", "😅", "☺️"],
    ("anger", "light"): ["💛", "😤"],
    ("disgust", "light"): ["💛", "😩"],
    ("neutral", "light"): ["💛", "🤍", "☺️"],
    ("neutral", "medium"): ["🤍"],
}


@dataclass
class SupportPlan:
    primary_emotion: str
    secondary_emotions: List[str]
    distress_intensity: int
    stage: str
    strategies: List[str]
    emoji: str
    tone_notes: str
    problem_hint: str
    user_goal: str
    should_ask_question: bool
    should_offer_action: bool
    response_style: str
    rationale: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _count_matches(text: str, patterns: List[str]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.I))


def _has_any(text: str, patterns: List[str]) -> bool:
    return _count_matches(text, patterns) > 0


def _last_user_messages(history: List[Tuple[str, str]], limit: int = 3) -> List[str]:
    msgs = [text for role, text in history if role != "model"]
    return msgs[-limit:]


def _recent_model_messages(history: List[Tuple[str, str]], limit: int = 2) -> List[str]:
    msgs = [text for role, text in history if role == "model"]
    return msgs[-limit:]


def _is_short_distress(text: str) -> bool:
    q = _norm(text)
    if q in SHORT_DISTRESS_SIGNALS:
        return True
    words = q.split()
    if len(words) <= 3 and any(q.startswith(p) for p in ("help", "please help", "i'm not")):
        return True
    return False


def detect_emotions(text: str) -> Tuple[str, List[str], Dict[str, int]]:
    q = _norm(text)
    scores: Dict[str, int] = {}

    for emotion, patterns in EMOTION_PATTERNS.items():
        score = _count_matches(q, patterns)
        if score:
            scores[emotion] = score

    if not scores:
        return "neutral", [], {"neutral": 1}

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    primary = ranked[0][0]
    secondary = [emo for emo, sc in ranked[1:3] if sc > 0]
    return primary, secondary, scores


def estimate_distress_intensity(text: str, risk_level: str = "low") -> int:
    q = _norm(text)

    if risk_level == "high":
        return 5
    if risk_level == "medium":
        return 4

    intensity = 2

    for level in sorted(INTENSITY_PATTERNS.keys(), reverse=True):
        if _has_any(q, INTENSITY_PATTERNS[level]):
            intensity = max(intensity, min(level, 4))

    if _is_short_distress(q):
        intensity = max(intensity, 3)

    if _has_any(q, [r"\bcan't\b", r"\bcannot\b", r"\bnever\b", r"\balways\b"]):
        intensity = max(intensity, 3)

    if _has_any(q, [r"\bpanic\b", r"\bworthless\b", r"\bnumb\b", r"\bheartbroken\b"]):
        intensity = max(intensity, 4)

    return max(1, min(5, intensity))


def detect_problem_hint(text: str) -> str:
    q = _norm(text)
    best_label = "general"
    best_score = 0

    for label, patterns in PROBLEM_HINTS.items():
        score = _count_matches(q, patterns)
        if score > best_score:
            best_score = score
            best_label = label

    return best_label


def infer_user_goal(text: str) -> str:
    q = _norm(text)

    if _has_any(q, ADVICE_PATTERNS + ACTION_READINESS_PATTERNS):
        return "wants_action"
    if _has_any(q, QUESTION_PATTERNS):
        return "seeking_guidance"
    if _has_any(q, VALIDATION_NEED_PATTERNS):
        return "needs_validation"
    return "needs_presence"


def conversation_progress(history: List[Tuple[str, str]]) -> float:
    user_turns = sum(1 for role, _ in history if role != "model")
    model_turns = sum(1 for role, _ in history if role == "model")
    turns = user_turns + model_turns
    if turns <= 2:
        return 0.1
    if turns <= 6:
        return 0.35
    if turns <= 10:
        return 0.65
    return 0.9


def user_has_shared_detail(history: List[Tuple[str, str]], current_text: str) -> bool:
    combined = " ".join(_last_user_messages(history, 3) + [current_text])
    return _has_any(combined, DETAIL_PATTERNS) or len(combined.split()) >= 18


def model_recently_asked_question(history: List[Tuple[str, str]]) -> bool:
    recent = " ".join(_recent_model_messages(history, 2))
    return "?" in recent


def choose_stage(
    history: List[Tuple[str, str]],
    user_message: str,
    primary_emotion: str,
    distress_intensity: int,
    risk_level: str = "low",
    problem_hint: str = "general",
) -> str:
    q = _norm(user_message)
    progress = conversation_progress(history)
    has_detail = user_has_shared_detail(history, q)
    wants_action = _has_any(q, ADVICE_PATTERNS + ACTION_READINESS_PATTERNS)

    if risk_level in {"high", "medium"}:
        return "comforting"

    if problem_hint == "romantic_rejection":
        return "comforting"

    if _has_any(q, POST_CRISIS_PATTERNS):
        return "comforting"

    if _has_any(q, COMFORT_OVERRIDE_PHRASES):
        return "comforting"

    if primary_emotion in ALWAYS_COMFORT_EMOTIONS:
        if wants_action and has_detail:
            return "action"
        return "comforting"

    if primary_emotion == "anxiety":
        if wants_action and has_detail:
            return "action"
        return "comforting"

    if progress <= 0.25 and not has_detail and not wants_action:
        return "exploration"

    if wants_action and has_detail:
        return "action"

    if primary_emotion == "anger":
        if has_detail and wants_action:
            return "action"
        return "comforting"

    if has_detail and progress >= 0.55:
        return "action"

    return "comforting"


def choose_strategies(
    stage: str,
    primary_emotion: str,
    distress_intensity: int,
    user_goal: str,
    risk_level: str = "low",
) -> List[str]:
    if risk_level == "high":
        return [
            "Reflection of Feelings",
            "Affirmation and Reassurance",
            "Information",
        ]

    if risk_level == "medium":
        return [
            "Reflection of Feelings",
            "Affirmation and Reassurance",
        ]

    if stage == "exploration":
        if primary_emotion in {"shame", "grief", "lonely", "sadness"}:
            return [
                "Reflection of Feelings",
                "Question",
                "Restatement or Paraphrasing",
            ]
        return [
            "Question",
            "Reflection of Feelings",
            "Restatement or Paraphrasing",
        ]

    if stage == "comforting":
        if primary_emotion == "anxiety":
            return [
                "Reflection of Feelings",
                "Affirmation and Reassurance",
                "Information",
            ]
        if primary_emotion in {"shame", "anger"}:
            return [
                "Reflection of Feelings",
                "Affirmation and Reassurance",
                "Restatement or Paraphrasing",
            ]
        return [
            "Reflection of Feelings",
            "Affirmation and Reassurance",
        ]

    if user_goal in {"wants_action", "seeking_guidance"} or distress_intensity <= 3:
        return [
            "Providing Suggestions",
            "Information",
            "Affirmation and Reassurance",
        ]

    return [
        "Affirmation and Reassurance",
        "Providing Suggestions",
    ]


def choose_emoji(
    primary_emotion: str,
    risk_level: str,
    distress_intensity: int,
    problem_hint: str,
    user_message: str = "",
) -> str:
    q = _norm(user_message)

    if risk_level in {"high", "medium"}:
        return ""
    if distress_intensity >= 4:
        return ""
    if problem_hint == "romantic_rejection":
        return ""
    if primary_emotion in HEAVY_EMOTIONS:
        return ""
    if _is_short_distress(q):
        return ""
    if _has_any(q, COMFORT_OVERRIDE_PHRASES):
        return ""
    if _has_any(q, POST_CRISIS_PATTERNS):
        return ""

    intensity_key = "light" if distress_intensity <= 2 else "medium"
    emoji_set = _EMOJI_BY_EMOTION.get((primary_emotion, intensity_key))

    if not emoji_set:
        emoji_set = _EMOJI_BY_EMOTION.get(("neutral", intensity_key), ["🤍"])

    return random.choice(emoji_set)


def should_ask_question(
    history: List[Tuple[str, str]],
    stage: str,
    user_goal: str,
    risk_level: str,
    distress_intensity: int,
) -> bool:
    if risk_level in {"high", "medium"}:
        return False
    if stage == "action" and user_goal == "wants_action":
        return False
    if stage == "exploration":
        return not model_recently_asked_question(history)
    if stage == "comforting":
        if distress_intensity >= 4:
            return False
        if model_recently_asked_question(history):
            return False
        return True
    return False


def should_offer_action(
    stage: str,
    user_goal: str,
    distress_intensity: int,
    risk_level: str,
) -> bool:
    if risk_level in {"high", "medium"}:
        return False
    if stage != "action":
        return False
    if distress_intensity >= 5:
        return False
    return user_goal in {"wants_action", "seeking_guidance"}


def build_tone_notes(
    primary_emotion: str,
    stage: str,
    distress_intensity: int,
    user_goal: str,
    risk_level: str,
    problem_hint: str,
) -> str:
    notes = []

    if risk_level == "high":
        return (
            "Be calm, direct, serious, and supportive. "
            "No emoji. No playful tone. "
            "Prioritize immediate safety and real-world help."
        )

    if risk_level == "medium":
        notes.append("Be grounded, steady, and careful.")
        notes.append("No emoji.")
        notes.append("No cute or playful phrasing.")
        notes.append("Do not ask a follow-up question.")
        if primary_emotion == "shame":
            notes.append("Be especially non-judgmental and reassuring.")
    else:
        notes.append("Use natural friend-like language.")
        notes.append("Never sound clinical, corporate, or lecture-like.")
        if distress_intensity <= 2:
            notes.append("A single gentle emoji is okay if it feels natural.")
        elif distress_intensity == 3:
            notes.append("Keep the tone warm and soft; emoji is optional but not necessary.")

    if problem_hint == "romantic_rejection":
        notes.append("Be warm and human.")
        notes.append("Acknowledge the sting of being ignored or rejected.")
        notes.append("No emoji for heartbreak.")
        notes.append("Do not sound flirty, cheerful, or polished.")

    if primary_emotion == "anxiety":
        notes.append("Use a steady grounding tone.")
        notes.append("Short lines.")
        notes.append("Help slow things down.")
    elif primary_emotion in {"grief", "sadness"}:
        notes.append("Be soft, gentle, and validating.")
        notes.append("Do not rush into solutions.")
    elif primary_emotion == "lonely":
        notes.append("Be warm, present, and companion-like.")
    elif primary_emotion == "shame":
        notes.append("Be careful, non-judgmental, and reassuring.")
    elif primary_emotion == "anger":
        notes.append("Acknowledge frustration without escalating.")
    elif primary_emotion == "fear":
        notes.append("Be steady and stabilizing.")

    if distress_intensity >= 4:
        notes.append("Keep the reply short.")
        notes.append("Focus on one emotional step only.")

    if stage == "exploration":
        notes.append("Lead with understanding.")
        notes.append("Ask at most one gentle open question.")
    elif stage == "comforting":
        notes.append("Name the feeling before anything else.")
        notes.append("Validation comes before advice.")
    elif stage == "action":
        notes.append("Offer only one small practical suggestion.")
        notes.append("Do not overload the user with options.")

    if user_goal == "needs_presence":
        notes.append("Do not force advice.")
    elif user_goal == "wants_action":
        notes.append("After validating, give a small next step.")

    return " ".join(notes)


def choose_response_style(
    primary_emotion: str,
    stage: str,
    distress_intensity: int,
    user_goal: str,
    risk_level: str,
    problem_hint: str,
) -> str:
    if risk_level == "high":
        return "safety-first"

    if risk_level == "medium":
        return "grounded-support"

    if problem_hint == "romantic_rejection":
        return "heartbreak_support"
    if primary_emotion == "anxiety":
        return "grounding"
    if primary_emotion == "lonely":
        return "loneliness_company"
    if primary_emotion in {"grief", "sadness"}:
        return "soft-companion"
    if primary_emotion == "shame":
        return "gentle-reassuring"
    if stage == "action":
        return "supportive-practical"
    if user_goal == "needs_presence":
        return "quiet-support"
    return "warm-support"


def build_esc_support_plan(
    history: List[Tuple[str, str]],
    user_message: str,
    risk_level: str = "low",
) -> dict:
    q = _norm(user_message)

    primary_emotion, secondary_emotions, emotion_scores = detect_emotions(q)
    distress_intensity = estimate_distress_intensity(q, risk_level)
    user_goal = infer_user_goal(q)
    problem_hint = detect_problem_hint(q)

    stage = choose_stage(
        history=history,
        user_message=q,
        primary_emotion=primary_emotion,
        distress_intensity=distress_intensity,
        risk_level=risk_level,
        problem_hint=problem_hint,
    )

    strategies = choose_strategies(
        stage=stage,
        primary_emotion=primary_emotion,
        distress_intensity=distress_intensity,
        user_goal=user_goal,
        risk_level=risk_level,
    )

    emoji = choose_emoji(
        primary_emotion=primary_emotion,
        risk_level=risk_level,
        distress_intensity=distress_intensity,
        problem_hint=problem_hint,
        user_message=q,
    )

    ask_question = should_ask_question(
        history=history,
        stage=stage,
        user_goal=user_goal,
        risk_level=risk_level,
        distress_intensity=distress_intensity,
    )

    offer_action = should_offer_action(
        stage=stage,
        user_goal=user_goal,
        distress_intensity=distress_intensity,
        risk_level=risk_level,
    )

    tone_notes = build_tone_notes(
        primary_emotion=primary_emotion,
        stage=stage,
        distress_intensity=distress_intensity,
        user_goal=user_goal,
        risk_level=risk_level,
        problem_hint=problem_hint,
    )

    response_style = choose_response_style(
        primary_emotion=primary_emotion,
        stage=stage,
        distress_intensity=distress_intensity,
        user_goal=user_goal,
        risk_level=risk_level,
        problem_hint=problem_hint,
    )

    rationale = [
        f"primary_emotion={primary_emotion}",
        f"secondary_emotions={','.join(secondary_emotions) if secondary_emotions else 'none'}",
        f"distress_intensity={distress_intensity}",
        f"user_goal={user_goal}",
        f"problem_hint={problem_hint}",
        f"stage={stage}",
        f"strategies={','.join(strategies)}",
    ]

    plan = SupportPlan(
        primary_emotion=primary_emotion,
        secondary_emotions=secondary_emotions,
        distress_intensity=distress_intensity,
        stage=stage,
        strategies=strategies,
        emoji=emoji,
        tone_notes=tone_notes,
        problem_hint=problem_hint,
        user_goal=user_goal,
        should_ask_question=ask_question,
        should_offer_action=offer_action,
        response_style=response_style,
        rationale=rationale,
    )

    return plan.to_dict()