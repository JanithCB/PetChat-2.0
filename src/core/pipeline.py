"""
src/core/pipeline.py -- Main chat-turn orchestrator for PetChat-2.0 v2.

Pipeline order:
1. Risk detection
2. High-risk safety fast path
3. Lightweight internal support plan
4. Mode-aware RAG
5. Optional memory context (stub for now)
6. Draft generation
7. Rewrite into friend-style reply
8. Emoji enforcement
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    if value in {"help_someone", "help someone", "guided_help", "guided help"}:
        return "help_someone"
    return "get_support"


def _trim_history(
    history: list[dict[str, str]],
    max_turns: int,
) -> list[dict[str, str]]:
    """
    Keep only the most recent max_turns pairs.
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
        content = str(item.get("content", "")).strip()

        if role not in {"user", "assistant", "system"}:
            continue
        if not content:
            continue

        cleaned.append({"role": role, "content": content})

    return cleaned


def _build_basic_support_plan(
    mode: str,
    user_message: str,
    history: list[dict[str, str]],
    risk_level: str,
    risk_tags: list[str],
) -> dict[str, Any]:
    """
    Lightweight fallback support planner used until esc_support.py is added.

    Returns a small dict compatible with prompts.py and pipeline emoji logic.
    """
    normalized_mode = _normalize_mode(mode)
    text = (user_message or "").lower()

    stage = "exploration"
    primary_emotion = "distress"
    response_style = "warm and grounded"
    strategies: list[str] = []
    use_emoji = risk_level == "low"

    if normalized_mode == "help_someone":
        primary_emotion = "concern"
        response_style = "supportive and practical"
        strategies = [
            "validate the user's concern for the other person",
            "give practical ways to support gently",
            "suggest when to encourage professional help",
        ]

        if any(word in text for word in ["suicide", "self-harm", "kill myself", "unsafe"]):
            stage = "safety_guidance"
            use_emoji = False
        elif any(word in text for word in ["how do i help", "what should i say", "what can i do"]):
            stage = "guidance"
        else:
            stage = "exploration"

    else:
        primary_emotion = "distress"
        response_style = "warm and empathetic"
        strategies = [
            "validate feelings",
            "gently reflect what the user is carrying",
            "offer one small next step if appropriate",
        ]

        if risk_level == "medium":
            stage = "stabilization"
            use_emoji = False
        elif any(word in text for word in ["anxious", "anxiety", "stress", "overwhelmed"]):
            primary_emotion = "anxiety"
            stage = "exploration"
        elif any(word in text for word in ["sad", "empty", "lonely", "worthless"]):
            primary_emotion = "sadness"
            stage = "exploration"
        elif any(word in text for word in ["angry", "mad", "frustrated", "upset"]):
            primary_emotion = "frustration"
            stage = "exploration"

    if "isolation" in risk_tags or "hopelessness" in risk_tags:
        use_emoji = False

    return {
        "stage": stage,
        "primary_emotion": primary_emotion,
        "secondary_emotion": "",
        "response_style": response_style,
        "goal": "support the user safely and naturally",
        "strategies": strategies,
        "follow_up_style": "one gentle follow-up question at most",
        "use_emoji": use_emoji,
    }


def _should_use_rag(mode: str) -> bool:
    """
    RAG is primarily used in Help Someone mode.
    """
    normalized = _normalize_mode(mode)

    try:
        from src.config import RAG_ENABLED  # noqa: PLC0415
        if not RAG_ENABLED:
            return False
    except Exception:
        return False

    return normalized == "help_someone"


def _build_rag_context(mode: str, user_message: str) -> tuple[str, bool]:
    """
    Build RAG context only when the current mode calls for it.
    """
    if not _should_use_rag(mode):
        return "", False

    try:
        from src.rag.retriever import build_rag_context  # noqa: PLC0415

        context = build_rag_context(user_message)
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


def _build_generation_messages(
    mode: str,
    history: list[dict[str, str]],
    user_message: str,
    plan: dict[str, Any],
    rag_context: str,
    memory_context: str,
    user_info: dict[str, Any] | None,
) -> list[dict[str, str]]:
    from src.config import MAX_HISTORY_TURNS  # noqa: PLC0415
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
    messages.extend(_trim_history(_sanitize_history(history), MAX_HISTORY_TURNS))
    messages.append({"role": "user", "content": user_message.strip()})
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
    return emoji_pattern.sub("", text or "").strip()


def _allow_emojis(plan: dict[str, Any], risk_level: str) -> bool:
    return bool(plan.get("use_emoji", False)) and risk_level == "low"


def _error_result(
    risk_level: str,
    risk_tags: list[str],
    plan: dict[str, Any],
    rag_used: bool,
    rag_context: str,
    error: str,
) -> dict[str, Any]:
    fallback = (
        "Something went wrong on my side just now. "
        "Please try again in a moment. "
        "I am still here with you."
    )

    return {
        "risk_level": risk_level,
        "risk_tags": risk_tags,
        "support_plan": plan,
        "rag_used": rag_used,
        "rag_context": rag_context,
        "draft_reply": fallback,
        "final_reply": fallback,
        "error": error,
    }


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
    from src.core.prompts import SAFETY_REPLY_HIGH, SAFETY_REPLY_MEDIUM  # noqa: PLC0415
    from src.core.providers import build_provider  # noqa: PLC0415
    from src.core.safety import detect_risk_level  # noqa: PLC0415

    normalized_mode = _normalize_mode(mode)
    clean_message = (user_message or "").strip()
    clean_history = _sanitize_history(history)

    if not clean_message:
        return {
            "risk_level": "low",
            "risk_tags": [],
            "support_plan": {},
            "rag_used": False,
            "rag_context": "",
            "draft_reply": "",
            "final_reply": "",
            "error": "Empty user_message.",
        }

    risk_level, risk_tags = detect_risk_level(clean_message)
    logger.info("Risk level=%s tags=%s mode=%s", risk_level, risk_tags, normalized_mode)

    if risk_level == "high":
        return {
            "risk_level": "high",
            "risk_tags": risk_tags,
            "support_plan": {},
            "rag_used": False,
            "rag_context": "",
            "draft_reply": SAFETY_REPLY_HIGH,
            "final_reply": SAFETY_REPLY_HIGH,
        }

    plan = _build_basic_support_plan(
        mode=normalized_mode,
        user_message=clean_message,
        history=clean_history,
        risk_level=risk_level,
        risk_tags=risk_tags,
    )

    rag_context, rag_used = _build_rag_context(normalized_mode, clean_message)
    memory_context, _memory_used = _build_memory_context(user_info or {})

    if risk_level == "medium" and not plan:
        return {
            "risk_level": risk_level,
            "risk_tags": risk_tags,
            "support_plan": {},
            "rag_used": rag_used,
            "rag_context": rag_context,
            "draft_reply": SAFETY_REPLY_MEDIUM,
            "final_reply": SAFETY_REPLY_MEDIUM,
        }

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

    try:
        draft_reply = provider.chat(
            generation_messages,
            temperature=0.75,
            max_tokens=420,
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
        )

    try:
        rewrite_messages = _build_rewrite_messages(
            mode=normalized_mode,
            draft=draft_reply,
            plan=plan,
            risk_level=risk_level,
        )
        final_reply = provider.chat(
            rewrite_messages,
            temperature=0.65,
            max_tokens=320,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rewrite failed, using draft: %s", exc)
        final_reply = draft_reply

    if not _allow_emojis(plan, risk_level):
        final_reply = _strip_emoji(final_reply)

    final_reply = final_reply.strip()

    return {
        "risk_level": risk_level,
        "risk_tags": risk_tags,
        "support_plan": plan,
        "rag_used": rag_used,
        "rag_context": rag_context,
        "draft_reply": (draft_reply or "").strip(),
        "final_reply": final_reply,
    }