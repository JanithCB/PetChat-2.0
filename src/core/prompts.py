"""
core/prompts.py -- Prompt building utilities for PetChat-2.0 v2.

This module keeps prompt logic small and composable:
- mode-neutral system guidance
- a few friend-style examples
- safety fallback replies
- helpers for generation and rewrite phases
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT: str = """You are PetChat, a warm and caring emotional support companion.
You speak like a calm, trusted friend.
You are supportive, grounded, and easy to talk to.

Rules you never break:
- Never diagnose, prescribe, or label the user or another person.
- Never claim to be a therapist, doctor, or crisis professional.
- Never minimise, shame, or dismiss feelings.
- Never use cold, academic, or clinical language.
- Never make up personal memories or facts not provided in context.
- In higher-risk situations, be calm, direct, and practical.
- Keep replies clear and natural, usually short enough to fit chat bubbles.
- Ask at most one gentle follow-up question when it helps.
- Do not start the reply with the word "I".
"""

FRIEND_STYLE_EXAMPLES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "I just feel so worthless lately. Like nothing I do matters.",
    },
    {
        "role": "assistant",
        "content": (
            "That sounds really heavy, and carrying that feeling for days can wear you down. "
            "Even if things feel pointless right now, what you are feeling still matters. "
            "What has been weighing on you most lately?"
        ),
    },
    {
        "role": "user",
        "content": "My anxiety is through the roof about my exams.",
    },
    {
        "role": "assistant",
        "content": (
            "That kind of exam stress can make your whole body feel on edge. "
            "When your mind will not slow down, even resting gets hard. "
            "Has it been getting worse recently, or has it felt this intense for a while?"
        ),
    },
    {
        "role": "user",
        "content": "My friend has been shutting everyone out and I do not know how to help.",
    },
    {
        "role": "assistant",
        "content": (
            "That is a hard place to be, especially when you care and do not want to push too hard. "
            "Being steady, kind, and patient can matter more than having perfect words. "
            "What changes have you noticed in them?"
        ),
    },
]

SAFETY_REPLY_HIGH: str = (
    "What you shared sounds serious, and your safety matters right now. "
    "Please contact a crisis line, emergency service, or a trusted person immediately and stay with someone if you can. "
    "If you are in Sri Lanka, you can contact Sumithrayo on 0800 111 000."
)

SAFETY_REPLY_MEDIUM: str = (
    "It sounds like things are feeling very intense right now. "
    "You do not have to carry that alone. "
    "Tell me what feels most urgent at this moment."
)


def _normalize_mode(mode: str | None) -> str:
    value = (mode or "").strip().lower()
    if value in {"help_someone", "help someone", "guided_help", "guided help"}:
        return "help_someone"
    return "get_support"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _optional_section(title: str, content: str | None) -> str:
    body = _safe_text(content)
    if not body:
        return ""
    return f"\n{title}:\n{body}\n"


def _format_user_info(user_info: dict[str, Any] | None) -> str:
    if not user_info:
        return ""

    allowed_keys = [
        "name",
        "preferred_name",
        "location",
        "age_range",
        "language",
        "notes",
    ]
    lines: list[str] = []

    for key in allowed_keys:
        value = _safe_text(user_info.get(key))
        if value:
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def _format_plan(plan: dict[str, Any] | None) -> str:
    if not plan:
        return "- none"

    lines: list[str] = []
    for key in [
        "stage",
        "primary_emotion",
        "secondary_emotion",
        "response_style",
        "goal",
        "strategies",
        "follow_up_style",
    ]:
        value = plan.get(key)
        if value is None or value == "":
            continue

        if isinstance(value, list):
            joined = ", ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                lines.append(f"- {key}: {joined}")
        else:
            text = str(value).strip()
            if text:
                lines.append(f"- {key}: {text}")

    return "\n".join(lines) if lines else "- none"


def _build_mode_instruction(mode: str) -> str:
    normalized = _normalize_mode(mode)

    if normalized == "help_someone":
        return (
            "Mode: Help Someone.\n"
            "The user is asking how to support another person.\n"
            "Treat the user as a caring helper, not as the main subject of the emotional issue.\n"
            "Give practical, compassionate guidance on how to respond, what to say, what to avoid, and when to encourage professional support.\n"
            "Keep the tone warm and non-clinical.\n"
            "Do not speak as if you have personally assessed the other person."
        )

    return (
        "Mode: Get Support.\n"
        "The user is speaking about their own thoughts, feelings, or struggles.\n"
        "Focus first on empathy, validation, and emotional steadiness.\n"
        "Offer one small helpful next step when appropriate.\n"
        "Keep the tone personal, warm, and non-clinical."
    )


def build_generation_system_prompt(
    mode: str,
    plan: dict[str, Any] | None,
    rag_context: str | None,
    memory_context: str | None,
    user_info: dict[str, Any] | None,
) -> str:
    """
    Build the generation-time system prompt for the first drafting pass.
    """
    mode_block = _build_mode_instruction(mode)
    plan_block = _format_plan(plan)
    user_block = _format_user_info(user_info)

    guidance = (
        "Reply like a close, emotionally intelligent friend.\n"
        "Lead with understanding before advice.\n"
        "Do not overload the reply with too many steps.\n"
        "If external guidance is provided, use it naturally without sounding like a textbook.\n"
        "Prefer short paragraphs or short chat-sized sentences.\n"
        "Do not use emojis unless later instructions explicitly allow them."
    )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{mode_block}\n\n"
        f"Support plan:\n{plan_block}\n\n"
        f"Generation guidance:\n{guidance}\n"
    )

    if user_block:
        prompt += f"\nKnown user info:\n{user_block}\n"

    prompt += _optional_section("Memory context", memory_context)
    prompt += _optional_section("Reference context", rag_context)

    return prompt.strip()


def build_rewrite_instruction(
    draft: str,
    plan: dict[str, Any] | None,
    risk_level: str,
    mode: str,
) -> str:
    """
    Build the rewrite instruction for the second pass that turns a draft
    into a more natural, friend-style final reply.
    """
    normalized_mode = _normalize_mode(mode)
    stage = _safe_text((plan or {}).get("stage")) or "support"
    style = _safe_text((plan or {}).get("response_style")) or "warm and grounded"
    use_emoji = bool((plan or {}).get("use_emoji")) and risk_level == "low"

    emoji_rule = (
        "You may add one small warm emoji only at the very end of the final sentence."
        if use_emoji
        else "Do not use any emojis."
    )

    if normalized_mode == "help_someone":
        mode_rule = (
            "Rewrite for a user who wants to support someone else. "
            "Sound encouraging and practical. "
            "Use wording like guidance for what the user can do or say, without sounding bossy."
        )
    else:
        mode_rule = (
            "Rewrite for a user seeking personal support. "
            "Sound emotionally present, reassuring, and gentle. "
            "Do not become overly instructional too quickly."
        )

    risk_rule = (
        "Because risk is high, keep the tone calm, direct, and safety-focused."
        if risk_level == "high"
        else "Because risk is medium, keep the tone steady, careful, and supportive."
        if risk_level == "medium"
        else "Risk is low, so the tone can stay soft, warm, and natural."
    )

    return (
        "Rewrite the draft below into a natural chat reply.\n"
        f"{mode_rule}\n"
        f"Support stage: {stage}.\n"
        f"Response style: {style}.\n"
        f"{risk_rule}\n"
        f"{emoji_rule}\n"
        "Keep it concise, human, and easy to read in chat bubbles.\n"
        "Avoid diagnosis, jargon, lectures, and repetitive reassurance.\n"
        "Do not start with the word 'I'.\n\n"
        f"Draft:\n{draft.strip()}\n\n"
        "Final rewritten reply:"
    )


__all__ = [
    "SYSTEM_PROMPT",
    "FRIEND_STYLE_EXAMPLES",
    "SAFETY_REPLY_HIGH",
    "SAFETY_REPLY_MEDIUM",
    "build_generation_system_prompt",
    "build_rewrite_instruction",
]