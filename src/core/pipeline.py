"""
src/core/pipeline.py -- Main chat-turn orchestrator for PetChat-2.0 v2.

Pipeline order:
1. Risk detection
2. High-risk safety fast path
3. Optional emotion classification
4. Lightweight internal support plan
5. Mode-aware RAG
6. Optional memory context (stub for now)
7. Draft generation
8. Rewrite into friend-style reply
9. Emoji enforcement
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

LOW = "low"
MEDIUM = "medium"
HIGH = "high"

GET_SUPPORT = "get_support"
HELP_SOMEONE = "help_someone"

_DRAFT_TEMPERATURE = 0.66
_REWRITE_TEMPERATURE = 0.44

_DEFAULT_DRAFT_MAX_TOKENS = 220
_DEFAULT_REWRITE_MAX_TOKENS = 180


def _normalize_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    if value in {"help_someone", "help someone", "guided_help", "guided help"}:
        return HELP_SOMEONE
    return GET_SUPPORT


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_reply_text(text: str | None) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""

    paragraphs = [re.sub(r"[ \t]+", " ", part).strip() for part in re.split(r"\n{2,}", raw)]
    paragraphs = [part for part in paragraphs if part]
    return "\n\n".join(paragraphs)


def _trim_history(
    history: list[dict[str, str]],
    max_turns: int,
) -> list[dict[str, str]]:
    """
    Keep only the most recent max_turns user/assistant pairs.
    """
    if max_turns <= 0:
        return []

    max_messages = max_turns * 2
    return history[-max_messages:] if len(history) > max_messages else history


def _sanitize_history(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    """
    Keep only chat-safe role/content pairs.
    """
    cleaned: list[dict[str, str]] = []

    for item in history or []:
        role = str(item.get("role", "")).strip()
        content = _normalize_text(str(item.get("content", "")))

        if role not in {"user", "assistant", "system"}:
            continue
        if not content:
            continue

        cleaned.append({"role": role, "content": content})

    return cleaned


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", _normalize_text(text).lower()))


def _is_greeting_turn(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    if text in {
        "hi",
        "hello",
        "hey",
        "hey there",
        "hiya",
        "yo",
        "sup",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "how r you",
        "hru",
    }:
        return True

    greeting_patterns = [
        r"^(hi|hello|hey+|hiya|yo)[.!]*$",
        r"^(good morning|good afternoon|good evening)[.!]*$",
        r"^(how are you|how r you|hru)[!?\.]*$",
    ]
    return _matches_any(text, greeting_patterns)


def _is_low_value_turn(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    return text in {
        "ok",
        "okay",
        "kk",
        "k",
        "thanks",
        "thank you",
        "thx",
        "got it",
        "cool",
        "alright",
        "all right",
        "makes sense",
        "fair",
        "understood",
    }


def _is_short_emotional_checkin(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    words = _word_count(text)

    if not text:
        return True

    guidance_patterns = [
        r"\bwhat should i do\b",
        r"\bwhat can i do\b",
        r"\bhow do i\b",
        r"\bhow can i\b",
        r"\bwhat should i say\b",
        r"\bcan you help me\b",
        r"\bany advice\b",
        r"\bany tips\b",
        r"\bhow to cope\b",
        r"\bhow to calm down\b",
        r"\bhow to handle\b",
        r"\bhow to support\b",
        r"\bwhat helps\b",
        r"\bwhat would help\b",
    ]
    if _matches_any(text, guidance_patterns):
        return False

    emotional_checkin_patterns = [
        r"\bi feel\b",
        r"\bi'm feeling\b",
        r"\bi am feeling\b",
        r"\bfeel really\b",
        r"\bfeel kinda\b",
        r"\bfeel so\b",
        r"\banxious\b",
        r"\bstressed\b",
        r"\boverwhelmed\b",
        r"\bsad\b",
        r"\bempty\b",
        r"\blonely\b",
        r"\bworthless\b",
        r"\bhopeless\b",
        r"\bconfused\b",
        r"\bnot okay\b",
        r"\bnot doing well\b",
        r"\brough day\b",
        r"\bbad day\b",
        r"\bjust tired\b",
        r"\bdrained\b",
        r"\bburned out\b",
        r"\bexhausted\b",
    ]

    return words <= 18 and _matches_any(text, emotional_checkin_patterns)


def _has_guidance_intent(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    guidance_patterns = [
        r"\bwhat should i do\b",
        r"\bwhat can i do\b",
        r"\bhow do i\b",
        r"\bhow can i\b",
        r"\bwhat should i say\b",
        r"\bcan you help me\b",
        r"\bany advice\b",
        r"\bany tips\b",
        r"\bhow to cope\b",
        r"\bhow to calm down\b",
        r"\bhow to handle\b",
        r"\bhow to deal with\b",
        r"\bwhat helps\b",
        r"\bwhat would help\b",
        r"\bgive me steps\b",
        r"\bpractical\b",
        r"\btechniques\b",
        r"\bstrategies\b",
        r"\bexercises\b",
        r"\bwhat do i say\b",
    ]
    return _matches_any(text, guidance_patterns)


def _has_helper_intent(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    helper_patterns = [
        r"\bmy friend\b",
        r"\bmy partner\b",
        r"\bmy boyfriend\b",
        r"\bmy girlfriend\b",
        r"\bmy wife\b",
        r"\bmy husband\b",
        r"\bmy sister\b",
        r"\bmy brother\b",
        r"\bmy mom\b",
        r"\bmy dad\b",
        r"\bsomeone i care about\b",
        r"\bsomeone close to me\b",
        r"\bthey have been\b",
        r"\bhe has been\b",
        r"\bshe has been\b",
        r"\bhow do i help\b",
        r"\bhow can i help\b",
        r"\bhow do i support\b",
        r"\bhow can i support\b",
        r"\bwhat should i say\b",
        r"\bwhat can i say\b",
        r"\bwithdrawing\b",
        r"\bshutting everyone out\b",
        r"\bwon't talk\b",
        r"\bwont talk\b",
    ]
    return _matches_any(text, helper_patterns)


def _has_emotional_content(user_message: str) -> bool:
    text = _normalize_text(user_message).lower()
    emotional_patterns = [
        r"\bi feel\b",
        r"\bi'm\b",
        r"\bi am\b",
        r"\banxious\b",
        r"\bstressed\b",
        r"\boverwhelmed\b",
        r"\bpanic\b",
        r"\bsad\b",
        r"\bempty\b",
        r"\blonely\b",
        r"\bworthless\b",
        r"\bhopeless\b",
        r"\bconfused\b",
        r"\bangry\b",
        r"\bmad\b",
        r"\bfrustrated\b",
        r"\bupset\b",
        r"\bdrained\b",
        r"\bexhausted\b",
        r"\bburned out\b",
        r"\bnot okay\b",
        r"\bnot doing well\b",
        r"\brough day\b",
        r"\bbad day\b",
    ]
    return _matches_any(text, emotional_patterns)


def _length_bucket(user_message: str) -> str:
    words = _word_count(user_message)
    if words <= 3:
        return "tiny"
    if words <= 12:
        return "short"
    if words <= 28:
        return "medium"
    return "long"


def _analyze_message_shape(
    mode: str,
    user_message: str,
    risk_level: str,
) -> dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
    text = _normalize_text(user_message)
    lowered = text.lower()
    words = _word_count(lowered)
    length_bucket = _length_bucket(lowered)

    greeting = _is_greeting_turn(lowered)
    low_value = _is_low_value_turn(lowered)
    helper_intent = _has_helper_intent(lowered)
    guidance_intent = _has_guidance_intent(lowered)
    emotional = _is_short_emotional_checkin(lowered) or _has_emotional_content(lowered)

    casual = (
        risk_level == LOW
        and not greeting
        and not low_value
        and not helper_intent
        and not guidance_intent
        and not emotional
        and words <= 12
    )

    if greeting:
        return {
            "message_kind": "greeting",
            "reply_length": "short",
            "ask_follow_up": True,
            "bubble_strategy": "question_split",
            "user_message_length": length_bucket,
            "tone_hint": "light and natural",
        }

    if low_value:
        return {
            "message_kind": "low_value",
            "reply_length": "short",
            "ask_follow_up": False,
            "bubble_strategy": "single",
            "user_message_length": length_bucket,
            "tone_hint": "warm and brief",
        }

    if normalized_mode == HELP_SOMEONE and (helper_intent or guidance_intent):
        return {
            "message_kind": "coaching",
            "reply_length": "long" if words >= 36 and risk_level == LOW else "medium",
            "ask_follow_up": risk_level == LOW and words <= 24,
            "bubble_strategy": "two_part" if risk_level == LOW and words <= 24 else "single",
            "user_message_length": length_bucket,
            "tone_hint": "practical and warm",
        }

    if guidance_intent:
        return {
            "message_kind": "guidance",
            "reply_length": "medium",
            "ask_follow_up": False,
            "bubble_strategy": "single",
            "user_message_length": length_bucket,
            "tone_hint": "clear and grounded",
        }

    if emotional:
        return {
            "message_kind": "emotional",
            "reply_length": "short" if words <= 18 and risk_level == LOW else "medium",
            "ask_follow_up": risk_level == LOW,
            "bubble_strategy": "question_split" if risk_level == LOW and words <= 16 else "single",
            "user_message_length": length_bucket,
            "tone_hint": "warm and validating",
        }

    if casual:
        return {
            "message_kind": "casual",
            "reply_length": "short",
            "ask_follow_up": words <= 8,
            "bubble_strategy": "question_split" if words <= 8 else "single",
            "user_message_length": length_bucket,
            "tone_hint": "light and companion-like",
        }

    return {
        "message_kind": "general",
        "reply_length": "medium" if words >= 20 else "short",
        "ask_follow_up": risk_level == LOW and words <= 10,
        "bubble_strategy": "question_split" if risk_level == LOW and words <= 10 else "single",
        "user_message_length": length_bucket,
        "tone_hint": "warm and steady",
    }


def _tone_hint_from_emotion(detected_emotion: str | None, fallback: str) -> str:
    mapping = {
        "sad": "soft, warm, and validating",
        "anxious": "steady, grounding, and not too long",
        "stressed": "calm, uncluttered, and containing",
        "angry": "calm, non-defensive, and containing",
        "confused": "clear, patient, and unhurried",
        "happy": "light, warm, and natural",
        "calm": "steady, natural, and lightly reassuring",
    }
    return mapping.get((detected_emotion or "").strip().lower(), fallback)


def _build_basic_support_plan(
    mode: str,
    user_message: str,
    history: list[dict[str, str]],
    risk_level: str,
    risk_tags: list[str],
    detected_emotion: str | None = None,
    emotion_confidence: float = 0.0,
) -> dict[str, Any]:
    """
    Lightweight fallback support planner used until a fuller planner is added.

    Returns a small dict compatible with prompts.py and pipeline emoji logic.
    """
    _ = history
    normalized_mode = _normalize_mode(mode)
    text = _normalize_text(user_message).lower()
    shape = _analyze_message_shape(normalized_mode, text, risk_level)

    stage = "exploration"
    primary_emotion = "distress"
    response_style = "warm and grounded"
    strategies: list[str] = []
    use_emoji = False

    normalized_detected_emotion = (detected_emotion or "").strip().lower() or None
    tone_hint = _tone_hint_from_emotion(normalized_detected_emotion, shape["tone_hint"])

    if normalized_mode == HELP_SOMEONE:
        primary_emotion = "concern"
        response_style = "supportive and practical"
        strategies = [
            "acknowledge the user's care or concern",
            "give practical ways to support gently",
            "suggest what the user could say in simple language",
            "help the user avoid pressure or fixing language",
            "suggest when to encourage professional or crisis help",
        ]

        if _contains_any(text, ["suicide", "self-harm", "kill myself", "unsafe", "emergency"]):
            stage = "safety_guidance"
            shape["reply_length"] = "medium"
            shape["ask_follow_up"] = False
        elif shape["message_kind"] == "greeting":
            stage = "connection"
            response_style = "warm, brief, and natural"
        elif shape["message_kind"] == "low_value":
            stage = "light_acknowledgement"
            response_style = "warm and brief"
        elif shape["message_kind"] == "coaching":
            stage = "guidance"
        elif _contains_any(
            text,
            ["withdrawing", "shutting everyone out", "isolating", "won't talk", "wont talk"],
        ):
            stage = "gentle_outreach"
        else:
            stage = "exploration"

        if normalized_detected_emotion == "anxious":
            response_style = "supportive, steady, and practical"
        elif normalized_detected_emotion == "stressed":
            response_style = "calm, practical, and containing"
        elif normalized_detected_emotion == "confused":
            response_style = "supportive, clear, and practical"
        elif normalized_detected_emotion == "angry":
            response_style = "calm, containing, and practical"
        elif normalized_detected_emotion == "sad":
            response_style = "warm, gentle, and practical"
        elif shape["message_kind"] in {"greeting", "low_value"}:
            response_style = "warm, brief, and natural"

    else:
        primary_emotion = "distress"
        response_style = "warm and empathetic"
        strategies = [
            "validate feelings first",
            "gently reflect what the user is carrying",
            "offer one small next step if appropriate",
        ]

        if risk_level == MEDIUM:
            stage = "stabilization"
            shape["reply_length"] = "medium"
        elif shape["message_kind"] == "greeting":
            stage = "connection"
            primary_emotion = "neutral"
            response_style = "warm, brief, and natural"
            strategies = [
                "reply briefly and naturally",
                "optionally ask one short follow-up question",
            ]
        elif shape["message_kind"] == "low_value":
            stage = "light_acknowledgement"
            primary_emotion = "neutral"
            response_style = "warm and brief"
            strategies = [
                "reply naturally",
                "do not over-extend the turn",
            ]
        elif shape["message_kind"] == "casual":
            stage = "casual_connection"
            primary_emotion = "light"
            response_style = "warm, natural, and lightly playful"
            strategies = [
                "match the size and energy of the message",
                "keep it brief and companion-like",
                "ask one light follow-up only if it helps",
            ]
        elif shape["message_kind"] == "guidance":
            stage = "guidance"
            primary_emotion = "distress"
            response_style = "clear, grounded, and supportive"
        elif _contains_any(text, ["anxious", "anxiety", "stress", "overwhelmed", "panic"]):
            primary_emotion = "anxiety"
            stage = "exploration"
        elif _contains_any(text, ["sad", "empty", "lonely", "worthless", "hopeless"]):
            primary_emotion = "sadness"
            stage = "exploration"
        elif _contains_any(text, ["angry", "mad", "frustrated", "upset"]):
            primary_emotion = "frustration"
            stage = "exploration"

        if normalized_detected_emotion == "sad":
            primary_emotion = "sadness"
            response_style = "very warm, gentle, and validating"
        elif normalized_detected_emotion == "anxious":
            primary_emotion = "anxiety"
            response_style = "calm, steady, and grounding"
        elif normalized_detected_emotion == "stressed":
            primary_emotion = "stress"
            response_style = "calm, grounding, and contained"
        elif normalized_detected_emotion == "angry":
            primary_emotion = "frustration"
            response_style = "calm, containing, and non-defensive"
        elif normalized_detected_emotion == "confused":
            primary_emotion = "confusion"
            response_style = "clear, patient, and unhurried"
        elif normalized_detected_emotion == "calm":
            primary_emotion = "calm"
            response_style = "warm, natural, and lightly reassuring"
        elif normalized_detected_emotion == "happy":
            primary_emotion = "positive"
            response_style = "warm, natural, and light"

    use_emoji = (
        risk_level == LOW
        and shape["message_kind"] in {"greeting", "casual"}
        and normalized_detected_emotion not in {"sad", "anxious", "stressed", "angry", "confused"}
    )

    if "isolation" in risk_tags or "hopelessness" in risk_tags or risk_level != LOW:
        use_emoji = False

    return {
        "stage": stage,
        "primary_emotion": primary_emotion,
        "secondary_emotion": "",
        "response_style": response_style,
        "goal": (
            "help the user support someone safely and naturally"
            if normalized_mode == HELP_SOMEONE
            else "support the user safely and naturally"
        ),
        "strategies": strategies,
        "follow_up_style": (
            "one gentle follow-up question at most"
            if shape["ask_follow_up"]
            else "no follow-up needed unless it clearly helps"
        ),
        "use_emoji": use_emoji,
        "detected_emotion": normalized_detected_emotion,
        "emotion_confidence": float(emotion_confidence or 0.0),
        "message_kind": shape["message_kind"],
        "reply_length": shape["reply_length"],
        "ask_follow_up": bool(shape["ask_follow_up"]),
        "bubble_strategy": shape["bubble_strategy"],
        "user_message_length": shape["user_message_length"],
        "tone_hint": tone_hint,
        "risk_level": risk_level,
    }


def _should_use_rag(
    mode: str,
    user_message: str,
    risk_level: str,
) -> bool:
    """
    Use RAG selectively.

    Priority:
    - Mostly for Help Someone turns
    - For longer, guidance-heavy Get Support turns
    - Not for greetings, tiny low-value turns, or short emotional check-ins
    """
    normalized_mode = _normalize_mode(mode)
    text = _normalize_text(user_message)
    lowered = text.lower()
    words = _word_count(lowered)
    shape = _analyze_message_shape(normalized_mode, lowered, risk_level)

    if not text or _is_low_value_turn(text) or shape["message_kind"] in {"greeting", "low_value", "casual"}:
        return False

    try:
        from src.config import RAG_ENABLED  # noqa: PLC0415

        if not RAG_ENABLED:
            return False
    except Exception:
        return False

    if risk_level == HIGH:
        return False

    if shape["message_kind"] == "emotional" and _is_short_emotional_checkin(lowered):
        return False

    if normalized_mode == HELP_SOMEONE:
        if shape["message_kind"] == "coaching":
            return True
        if words >= 16 and _has_guidance_intent(lowered):
            return True
        return False

    if normalized_mode == GET_SUPPORT:
        if shape["message_kind"] == "guidance" and words >= 12:
            return True
        if risk_level == MEDIUM and words >= 24:
            return True
        return False

    return False


def _build_rag_query(
    mode: str,
    user_message: str,
    risk_level: str,
) -> str:
    text = _normalize_text(user_message)
    lowered = text.lower()

    guidance_patterns = [
        r"\bwhat should i do\b",
        r"\bwhat can i do\b",
        r"\bhow do i\b",
        r"\bhow can i\b",
        r"\bwhat should i say\b",
        r"\bhow to cope\b",
        r"\bhow to calm down\b",
        r"\bhow to handle\b",
        r"\bhow to deal with\b",
        r"\bwhat helps\b",
        r"\bpractical steps\b",
        r"\bexercises\b",
        r"\btechniques\b",
    ]

    if _normalize_mode(mode) == HELP_SOMEONE:
        return f"how to support someone what to say practical help {text}"

    if _matches_any(lowered, guidance_patterns):
        return f"coping strategies grounding practical support steps {text}"

    if risk_level == MEDIUM:
        return f"emotional support grounding coping steps {text}"

    return text


def _build_rag_context(mode: str, user_message: str, risk_level: str) -> tuple[str, bool]:
    """
    Build RAG context only when the current mode/turn calls for it.
    """
    if not _should_use_rag(mode, user_message, risk_level):
        return "", False

    try:
        from src.rag.rag_engine import build_rag_context  # noqa: PLC0415

        normalized_mode = _normalize_mode(mode)
        query = _build_rag_query(normalized_mode, user_message, risk_level)

        max_chunks = 2 if normalized_mode == HELP_SOMEONE else 1
        max_chars = 1500 if normalized_mode == HELP_SOMEONE else 850
        min_score = 0.20 if risk_level == MEDIUM else 0.22

        context = build_rag_context(
            query=query,
            max_chunks=max_chunks,
            min_score=min_score,
            max_chars=max_chars,
        )
        context = context.strip() if isinstance(context, str) else ""
        return context, bool(context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG context failed: %s", exc)
        return "", False


def _build_memory_context(
    user_info: dict[str, Any] | None,
) -> tuple[str, bool]:
    """
    Stub for future Supabase memory integration.
    """
    try:
        from src.config import USE_SUPABASE_MEMORY  # noqa: PLC0415

        if not USE_SUPABASE_MEMORY:
            return "", False
    except Exception:
        return "", False

    _ = user_info or {}
    return "", False


def _get_max_history_turns(default: int = 6) -> int:
    try:
        from src.config import MAX_HISTORY_TURNS  # noqa: PLC0415

        value = int(MAX_HISTORY_TURNS)
        return value if value >= 0 else default
    except Exception:
        return default


def _build_generation_messages(
    mode: str,
    history: list[dict[str, str]],
    user_message: str,
    plan: dict[str, Any],
    rag_context: str,
    memory_context: str,
    user_info: dict[str, Any] | None,
) -> list[dict[str, str]]:
    from src.core.prompts import (  # noqa: PLC0415
        FRIEND_STYLE_EXAMPLES,
        build_generation_system_prompt,
    )

    system_prompt = build_generation_system_prompt(
        mode=mode,
        plan=plan,
        rag_context=rag_context,
        memory_context=memory_context,
        user_info=user_info or {},
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    messages.extend(FRIEND_STYLE_EXAMPLES)
    messages.extend(_trim_history(history, _get_max_history_turns()))
    messages.append({"role": "user", "content": _normalize_text(user_message)})
    return messages


def _build_rewrite_messages(
    mode: str,
    draft: str,
    plan: dict[str, Any],
    risk_level: str,
) -> list[dict[str, str]]:
    from src.core.prompts import SYSTEM_PROMPT, build_rewrite_instruction  # noqa: PLC0415

    rewrite_instruction = build_rewrite_instruction(
        draft=draft,
        plan=plan,
        risk_level=risk_level,
        mode=mode,
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": rewrite_instruction},
    ]


def _strip_emoji(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    cleaned = emoji_pattern.sub("", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" ?\n ?", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _allow_emojis(plan: dict[str, Any], risk_level: str) -> bool:
    if risk_level != LOW:
        return False
    if plan.get("message_kind") not in {"greeting", "casual"}:
        return False
    return bool(plan.get("use_emoji", False))


def _trim_output(text: str, max_chars: int) -> str:
    clean = _normalize_reply_text(text)
    if len(clean) <= max_chars:
        return clean

    chunks = [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]
    kept: list[str] = []
    total = 0

    for chunk in chunks:
        extra = len(chunk) + (2 if kept else 0)
        if total + extra <= max_chars:
            kept.append(chunk)
            total += extra
            continue

        remaining = max_chars - total - (2 if kept else 0)
        if remaining > 24:
            clipped = chunk[:remaining].rsplit(" ", 1)[0].strip()
            if clipped:
                kept.append(f"{clipped}...")
        break

    if kept:
        return "\n\n".join(kept).strip()

    fallback = clean[:max_chars].rsplit(" ", 1)[0].strip()
    return f"{fallback}..." if fallback else clean[:max_chars]


def _enforce_short_shape(text: str, plan: dict[str, Any], risk_level: str) -> str:
    clean = _normalize_reply_text(text)
    if not clean:
        return ""

    kind = str(plan.get("message_kind", "")).strip().lower()
    reply_length = str(plan.get("reply_length", "")).strip().lower()
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]

    if kind == "low_value":
        return paragraphs[0] if paragraphs else clean

    if kind in {"greeting", "casual"}:
        if len(paragraphs) > 2:
            paragraphs = paragraphs[:2]
        compact = "\n\n".join(paragraphs)
        return _trim_output(compact, 170 if kind == "greeting" else 220)

    if kind == "emotional" and reply_length == "short" and risk_level == LOW:
        if len(paragraphs) > 2:
            paragraphs = paragraphs[:2]
        compact = "\n\n".join(paragraphs)
        return _trim_output(compact, 300)

    return clean


def _draft_max_tokens(
    mode: str,
    risk_level: str,
    rag_used: bool,
    plan: dict[str, Any],
) -> int:
    kind = str(plan.get("message_kind", "")).strip().lower()
    reply_length = str(plan.get("reply_length", "")).strip().lower()

    if risk_level == MEDIUM:
        if kind in {"greeting", "low_value"}:
            return 90
        return 190

    if kind in {"greeting", "low_value"}:
        return 80
    if kind == "casual":
        return 95
    if kind == "emotional" and reply_length == "short":
        return 130
    if kind == "guidance":
        return 180
    if kind == "coaching":
        if rag_used and _normalize_mode(mode) == HELP_SOMEONE:
            return 235 if reply_length == "long" else 215
        return 210 if reply_length == "long" else 185

    return _DEFAULT_DRAFT_MAX_TOKENS


def _rewrite_max_tokens(risk_level: str, plan: dict[str, Any]) -> int:
    kind = str(plan.get("message_kind", "")).strip().lower()
    reply_length = str(plan.get("reply_length", "")).strip().lower()

    if risk_level == MEDIUM:
        return 155

    if kind in {"greeting", "low_value"}:
        return 70
    if kind == "casual":
        return 85
    if kind == "emotional" and reply_length == "short":
        return 120
    if kind == "coaching":
        return 190 if reply_length == "long" else 165
    if kind == "guidance":
        return 150

    return _DEFAULT_REWRITE_MAX_TOKENS


def _final_max_chars(mode: str, risk_level: str, plan: dict[str, Any]) -> int:
    normalized_mode = _normalize_mode(mode)
    kind = str(plan.get("message_kind", "")).strip().lower()
    reply_length = str(plan.get("reply_length", "")).strip().lower()

    if risk_level == MEDIUM:
        return 440

    if kind in {"greeting", "low_value"}:
        return 150
    if kind == "casual":
        return 220
    if kind == "emotional" and reply_length == "short":
        return 300
    if kind == "guidance":
        return 420
    if kind == "coaching":
        if normalized_mode == HELP_SOMEONE and reply_length == "long":
            return 700
        return 560

    return 420 if normalized_mode == GET_SUPPORT else 520


def _fallback_reply(risk_level: str, mode: str) -> str:
    from src.core.prompts import SAFETY_REPLY_MEDIUM  # noqa: PLC0415

    if risk_level == MEDIUM:
        return SAFETY_REPLY_MEDIUM

    if _normalize_mode(mode) == HELP_SOMEONE:
        return (
            "Hey, that sounds really hard. "
            "You do not need perfect words here. "
            "A simple message like 'I care about you, and I am here' is often a good place to start."
        )

    return (
        "Hey, that sounds really hard right now. "
        "We can stay with the most important part first and take it one step at a time."
    )


def _error_result(
    risk_level: str,
    risk_tags: list[str],
    plan: dict[str, Any],
    rag_used: bool,
    rag_context: str,
    error: str,
    mode: str,
    emotion_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = _fallback_reply(risk_level, mode)

    return {
        "risk_level": risk_level,
        "risk_tags": risk_tags,
        "support_plan": plan,
        "rag_used": rag_used,
        "rag_context": rag_context,
        "draft_reply": fallback,
        "final_reply": fallback,
        "error": error,
        "emotion_result": emotion_result or {},
        "detected_emotion": (plan or {}).get("detected_emotion"),
    }


def _looks_like_wrong_help_someone_perspective(text: str, user_message: str) -> bool:
    """
    Detect common cases where the model answers as if the user is the distressed
    person instead of the helper.
    """
    reply = _normalize_text(text).lower()
    user = _normalize_text(user_message).lower()

    if not reply:
        return False

    bad_patterns = [
        "i'm here with you",
        "i am here with you",
        "you are not alone",
        "what you're feeling",
        "what you are feeling",
        "you matter",
        "you've been through",
        "you have been through",
        "reach out when these feelings come up",
        "after losing your friend",
        "i'm here now as well",
        "i am here now as well",
        "tell me what has been hitting the hardest",
    ]

    helper_signals = [
        "you could say",
        "you can say",
        "try saying",
        "let them know",
        "check in with them",
        "reach out to them",
        "be there for them",
        "support them",
        "ask them",
    ]

    if any(signal in reply for signal in helper_signals):
        return False

    if any(pattern in reply for pattern in bad_patterns):
        return True

    if "my friend" in user and "your friend" in reply and "losing your friend" in reply:
        return True

    return False


def _rewrite_help_someone_repair(
    provider: Any,
    draft_reply: str,
    user_message: str,
    plan: dict[str, Any],
    risk_level: str,
) -> str:
    """
    One lightweight repair pass if the rewrite drifts into the wrong perspective.
    """
    _ = plan

    repair_instruction = (
        "Rewrite this reply so it clearly speaks to the user as a helper supporting another person.\n"
        "Keep the helper perspective intact.\n"
        "Do not talk as if the user is the depressed or distressed person.\n"
        "Do not address the third person as if they are chatting with you.\n"
        "Do not say things like 'I am here with you' to the struggling friend.\n"
        "Give warm, practical wording, and include one simple line the user could say if helpful.\n"
        "Keep it concise, natural, and chat-friendly.\n"
        "Do not start with the word 'I'.\n\n"
        f"User message:\n{_normalize_text(user_message)}\n\n"
        f"Current reply:\n{_normalize_reply_text(draft_reply)}\n\n"
        "Fixed reply:"
    )

    try:
        repaired = provider.chat(
            [
                {"role": "system", "content": "You are rewriting a reply to preserve the correct perspective."},
                {"role": "user", "content": repair_instruction},
            ],
            temperature=0.30,
            max_tokens=180 if risk_level == LOW else 160,
        )
        return _normalize_reply_text(repaired)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Helper-perspective repair failed: %s", exc)
        return _normalize_reply_text(draft_reply)


def run_chat_turn(
    mode: str,
    session_config: dict[str, Any],
    history: list[dict[str, Any]],
    user_message: str,
    user_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Run one full PetChat turn.

    Parameters
    ----------
    mode:
        "get_support" or "help_someone"
    session_config:
        Provider/model config emitted by UI or CLI
    history:
        Prior chat messages as role/content dicts
    user_message:
        Latest user input
    user_info:
        Optional user metadata

    Returns
    -------
    dict with:
        risk_level, risk_tags, support_plan,
        rag_used, rag_context, draft_reply, final_reply
    """
    from src.core.prompts import SAFETY_REPLY_HIGH  # noqa: PLC0415
    from src.core.providers import build_provider  # noqa: PLC0415
    from src.core.safety import detect_risk_level  # noqa: PLC0415
    from src.core.emotion_classifier import classify_emotion  # noqa: PLC0415

    normalized_mode = _normalize_mode(mode)
    clean_message = _normalize_text(user_message)
    clean_history = _sanitize_history(history)

    if not clean_message:
        return {
            "risk_level": LOW,
            "risk_tags": [],
            "support_plan": {},
            "rag_used": False,
            "rag_context": "",
            "draft_reply": "",
            "final_reply": "",
            "error": "Empty user_message.",
            "emotion_result": {},
            "detected_emotion": None,
        }

    risk_level, risk_tags = detect_risk_level(clean_message)
    logger.info("Risk level=%s tags=%s mode=%s", risk_level, risk_tags, normalized_mode)

    if risk_level == HIGH:
        return {
            "risk_level": HIGH,
            "risk_tags": risk_tags,
            "support_plan": {},
            "rag_used": False,
            "rag_context": "",
            "draft_reply": SAFETY_REPLY_HIGH,
            "final_reply": SAFETY_REPLY_HIGH,
            "emotion_result": {},
            "detected_emotion": None,
        }

    emotion_result: dict[str, Any] = {}
    emotion_label = None
    emotion_confidence = 0.0

    try:
        raw_emotion_result = classify_emotion(clean_message)
        if isinstance(raw_emotion_result, dict):
            emotion_result = raw_emotion_result
            if raw_emotion_result.get("ok"):
                emotion_label = str(raw_emotion_result.get("label", "")).strip().lower() or None
                emotion_confidence = float(raw_emotion_result.get("confidence", 0.0) or 0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Emotion classifier failed, continuing safely: %s", exc)
        emotion_result = {
            "ok": False,
            "label": None,
            "confidence": 0.0,
            "error": str(exc),
        }

    logger.info(
        "Emotion result ok=%s label=%s confidence=%.3f",
        emotion_result.get("ok") if isinstance(emotion_result, dict) else None,
        emotion_label,
        emotion_confidence,
    )

    plan = _build_basic_support_plan(
        mode=normalized_mode,
        user_message=clean_message,
        history=clean_history,
        risk_level=risk_level,
        risk_tags=risk_tags,
        detected_emotion=emotion_label,
        emotion_confidence=emotion_confidence,
    )

    rag_context, rag_used = _build_rag_context(
        mode=normalized_mode,
        user_message=clean_message,
        risk_level=risk_level,
    )
    memory_context, _memory_used = _build_memory_context(user_info or {})

    try:
        provider = build_provider(session_config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Provider build failed: %s", exc)
        return _error_result(
            risk_level=risk_level,
            risk_tags=risk_tags,
            plan=plan,
            rag_used=rag_used,
            rag_context=rag_context,
            error=str(exc),
            mode=normalized_mode,
            emotion_result=emotion_result,
        )

    generation_messages = _build_generation_messages(
        mode=normalized_mode,
        history=clean_history,
        user_message=clean_message,
        plan=plan,
        rag_context=rag_context,
        memory_context=memory_context,
        user_info=user_info or {},
    )

    draft_reply = ""
    try:
        draft_reply = provider.chat(
            generation_messages,
            temperature=_DRAFT_TEMPERATURE,
            max_tokens=_draft_max_tokens(
                mode=normalized_mode,
                risk_level=risk_level,
                rag_used=rag_used,
                plan=plan,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Draft generation failed: %s", exc)
        return _error_result(
            risk_level=risk_level,
            risk_tags=risk_tags,
            plan=plan,
            rag_used=rag_used,
            rag_context=rag_context,
            error=str(exc),
            mode=normalized_mode,
            emotion_result=emotion_result,
        )

    draft_reply = _trim_output(draft_reply, max_chars=max(260, _final_max_chars(normalized_mode, risk_level, plan) + 120))
    draft_reply = _enforce_short_shape(draft_reply, plan, risk_level)

    try:
        rewrite_messages = _build_rewrite_messages(
            mode=normalized_mode,
            draft=draft_reply,
            plan=plan,
            risk_level=risk_level,
        )
        final_reply = provider.chat(
            rewrite_messages,
            temperature=_REWRITE_TEMPERATURE,
            max_tokens=_rewrite_max_tokens(risk_level, plan),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rewrite failed, using draft: %s", exc)
        final_reply = draft_reply

    final_reply = _trim_output(final_reply, max_chars=_final_max_chars(normalized_mode, risk_level, plan))
    final_reply = _enforce_short_shape(final_reply, plan, risk_level)

    if normalized_mode == HELP_SOMEONE and _looks_like_wrong_help_someone_perspective(
        final_reply,
        clean_message,
    ):
        logger.warning("Detected wrong helper-mode perspective; running repair rewrite.")
        final_reply = _rewrite_help_someone_repair(
            provider=provider,
            draft_reply=final_reply,
            user_message=clean_message,
            plan=plan,
            risk_level=risk_level,
        )
        final_reply = _trim_output(final_reply, max_chars=_final_max_chars(normalized_mode, risk_level, plan))
        final_reply = _enforce_short_shape(final_reply, plan, risk_level)

    if not _allow_emojis(plan, risk_level):
        final_reply = _strip_emoji(final_reply)

    final_reply = _normalize_reply_text(final_reply)
    final_reply = final_reply.strip() or _fallback_reply(risk_level, normalized_mode)

    return {
        "risk_level": risk_level,
        "risk_tags": risk_tags,
        "support_plan": plan,
        "rag_used": rag_used,
        "rag_context": rag_context,
        "draft_reply": _normalize_reply_text(draft_reply),
        "final_reply": final_reply,
        "emotion_result": emotion_result,
        "detected_emotion": plan.get("detected_emotion"),
    }