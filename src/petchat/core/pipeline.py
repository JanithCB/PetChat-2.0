"""
core/pipeline.py -- Main chat-turn orchestrator for PetChat-2.0.

Pipeline steps
--------------
1. detect_risk_level
2. build_esc_support_plan  (skipped for high-risk)
3. build_rag_context       (skipped when RAG_ENABLED=False)
4. load Supabase context   (skipped when SUPABASE disabled)
5. generate draft reply
6. rewrite into friend-style reply
7. return structured result dict
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_rag_context(user_message: str) -> tuple[str, bool]:
    try:
        from petchat.config import RAG_ENABLED  # noqa: PLC0415
        if not RAG_ENABLED:
            return "", False
        from petchat.rag.retriever import build_rag_context  # noqa: PLC0415
        ctx = build_rag_context(user_message)
        return ctx, bool(ctx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG context failed: %s", exc)
        return "", False


def _build_memory_context(user_info: dict[str, str]) -> tuple[str, bool]:
    try:
        from petchat.config import USE_SUPABASE_MEMORY  # noqa: PLC0415
        if not USE_SUPABASE_MEMORY:
            return "", False
        from petchat.memory.conversation_store import load_user_summary  # noqa: PLC0415
        summary = load_user_summary(user_info.get("user_id", ""))
        return summary, bool(summary)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Memory context skipped: %s", exc)
        return "", False


def _trim_history(
    history: list[dict[str, str]],
    max_turns: int,
) -> list[dict[str, str]]:
    """Keep only the most recent max_turns pairs (2 * max_turns messages)."""
    max_messages = max_turns * 2
    return history[-max_messages:] if len(history) > max_messages else history


def _build_generation_messages(
    user_message: str,
    history: list[dict[str, str]],
    plan: dict,
    rag_context: str,
    memory_context: str,
    user_info: dict[str, str],
) -> list[dict[str, str]]:
    from petchat.core.prompts import SYSTEM_PROMPT, FRIEND_STYLE_EXAMPLES  # noqa: PLC0415
    from petchat.config import MAX_HISTORY_TURNS  # noqa: PLC0415

    system_parts = [SYSTEM_PROMPT.strip()]

    if memory_context:
        system_parts.append(
            f"\n[WHAT YOU KNOW ABOUT THIS USER]\n{memory_context.strip()}"
        )

    if rag_context:
        system_parts.append(
            f"\n[RELEVANT WELLBEING INFORMATION]\n{rag_context.strip()}"
        )

    system_parts.append(
        f"\n[CURRENT SUPPORT PLAN]"
        f"\nStage: {plan.get('stage', 'exploration')}"
        f"\nEmotion: {plan.get('primary_emotion', 'distress')}"
        f"\nStyle: {plan.get('response_style', 'warm and empathetic')}"
        f"\nStrategies: {', '.join(plan.get('strategies', []))}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": "\n".join(system_parts)}
    ]
    messages.extend(FRIEND_STYLE_EXAMPLES)
    messages.extend(_trim_history(history, MAX_HISTORY_TURNS))
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_rewrite_messages(
    draft: str,
    plan: dict,
    risk_level: str,
) -> list[dict[str, str]]:
    from petchat.core.prompts import SYSTEM_PROMPT, build_rewrite_instruction  # noqa: PLC0415
    instruction = build_rewrite_instruction(draft, plan, risk_level)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user",   "content": instruction},
    ]


def _strip_emoji(text: str) -> str:
    import re  # noqa: PLC0415
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002500-\U00002BEF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_chat_turn(
    session_config: dict[str, Any],
    history: list[dict[str, str]],
    user_message: str,
    user_info: dict[str, str],
) -> dict[str, Any]:
    """
    Run one full chat turn through the PetChat pipeline.

    Parameters
    ----------
    session_config : Provider/model config dict (from ModelSetupPage or CLI).
    history        : List of {"role": ..., "content": ...} dicts (prior turns).
    user_message   : The latest user message string.
    user_info      : Dict with user_id, user_name, session_id.

    Returns
    -------
    dict with keys:
        risk_level, risk_tags, support_plan,
        rag_used, rag_context, memory_used,
        draft_reply, final_reply
    """
    from petchat.core.safety import detect_risk_level          # noqa: PLC0415
    from petchat.core.esc_support import build_esc_support_plan  # noqa: PLC0415
    from petchat.core.prompts import SAFETY_REPLY_HIGH, SAFETY_REPLY_MEDIUM  # noqa: PLC0415
    from petchat.core.providers import build_provider           # noqa: PLC0415

    # ── Step 1: Risk detection ────────────────────────────────────────────
    risk_level, risk_tags = detect_risk_level(user_message)
    logger.info("Risk: %s  tags: %s", risk_level, risk_tags)

    # ── Step 2: High-risk fast path ───────────────────────────────────────
    if risk_level == "high":
        return {
            "risk_level":   "high",
            "risk_tags":    risk_tags,
            "support_plan": {},
            "rag_used":     False,
            "rag_context":  "",
            "memory_used":  False,
            "draft_reply":  SAFETY_REPLY_HIGH,
            "final_reply":  SAFETY_REPLY_HIGH,
        }

    # ── Step 3: Support plan ──────────────────────────────────────────────
    plan = build_esc_support_plan(
        user_message=user_message,
        history=history,
        risk_level=risk_level,
        risk_tags=risk_tags,
    )
    logger.info("Plan: stage=%s emotion=%s", plan["stage"], plan["primary_emotion"])

    # ── Step 4: RAG context ───────────────────────────────────────────────
    rag_context, rag_used = _build_rag_context(user_message)

    # ── Step 5: Long-term memory context ─────────────────────────────────
    memory_context, memory_used = _build_memory_context(user_info)

    # ── Step 6: Build provider ────────────────────────────────────────────
    try:
        provider = build_provider(session_config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Provider build failed: %s", exc)
        return _error_result(risk_level, risk_tags, plan, rag_context, str(exc))

    # ── Step 7: Generate draft ────────────────────────────────────────────
    gen_messages = _build_generation_messages(
        user_message=user_message,
        history=history,
        plan=plan,
        rag_context=rag_context,
        memory_context=memory_context,
        user_info=user_info,
    )

    try:
        draft = provider.chat(gen_messages, temperature=0.75, max_tokens=400)
    except Exception as exc:  # noqa: BLE001
        logger.error("Generation failed: %s", exc)
        return _error_result(risk_level, risk_tags, plan, rag_context, str(exc))

    # ── Step 8: Rewrite into friend-style ────────────────────────────────
    try:
        rewrite_messages = _build_rewrite_messages(draft, plan, risk_level)
        final_reply = provider.chat(rewrite_messages, temperature=0.65, max_tokens=300)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rewrite failed (%s) — using draft.", exc)
        final_reply = draft

    # Strip emojis if plan says no emoji
    if not plan.get("use_emoji", False):
        final_reply = _strip_emoji(final_reply)

    # Medium risk: strip emoji always
    if risk_level == "medium":
        final_reply = _strip_emoji(final_reply)

    return {
        "risk_level":   risk_level,
        "risk_tags":    risk_tags,
        "support_plan": plan,
        "rag_used":     rag_used,
        "rag_context":  rag_context,
        "memory_used":  memory_used,
        "draft_reply":  draft,
        "final_reply":  final_reply.strip(),
    }


def _error_result(
    risk_level: str,
    risk_tags: list[str],
    plan: dict,
    rag_context: str,
    error: str,
) -> dict[str, Any]:
    fallback = (
        "Something went wrong on my end. "
        "Please try again in a moment -- I'm still here with you."
    )
    return {
        "risk_level":   risk_level,
        "risk_tags":    risk_tags,
        "support_plan": plan,
        "rag_used":     bool(rag_context),
        "rag_context":  rag_context,
        "memory_used":  False,
        "draft_reply":  fallback,
        "final_reply":  fallback,
        "error":        error,
    }