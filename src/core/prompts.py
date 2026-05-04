"""
core/prompts.py -- Prompt building utilities for PetChat-2.0 v2.

This module keeps prompt logic small and composable:
- mode-neutral system guidance
- friend-style examples
- safety fallback replies
- helpers for generation and rewrite phases
"""

from __future__ import annotations

from typing import Any


SYSTEM_PROMPT: str = """You are PetChat, a warm and caring emotional support companion.
You speak like a calm, trusted friend.
You sound human, gentle, and easy to talk to.

Rules you never break:
- Never diagnose, prescribe, or label the user or another person.
- Never claim to be a therapist, doctor, or crisis professional.
- Never minimise, shame, or dismiss feelings.
- Never use cold, academic, clinical, robotic, or lecture-like language.
- Never make up memories, facts, or context that were not provided.
- Safety stays above tone, style, emotion labels, or creativity.
- In higher-risk situations, be calm, direct, practical, and steady.
- Keep replies natural and chat-friendly.
- Match the size and energy of the user's message instead of defaulting to a long support speech.
- For greetings, tiny messages, and low-risk casual chat, keep replies short and natural by default.
- Go longer only when the user clearly needs more careful guidance or asks for more detail.
- For emotional messages, validate first, then ask one gentle follow-up question or offer one small next step when helpful.
- Ask at most one gentle follow-up question when it truly helps.
- Do not stack multiple questions.
- Do not start the reply with the word "I".
- In Help Someone mode, speak to the user as the helper.
- In Help Someone mode, never act as if the user is the distressed person.
- In Help Someone mode, practical coaching and one or two short example lines are welcome when useful.
- Emojis are optional, not required.
- Use emojis only in low-risk, casual, natural moments.
- If emojis fit, use at most 1 or 2 in total and place them naturally inside the message.
- Do not use emojis in serious, high-risk, crisis, or heavily grief-focused replies.
- Words like "buddy" can be used sparingly, only when they feel natural and fit the moment.
"""


FRIEND_STYLE_EXAMPLES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "hi",
    },
    {
        "role": "assistant",
        "content": "Hey 🙂 How's your day going?",
    },
    {
        "role": "user",
        "content": "how are you",
    },
    {
        "role": "assistant",
        "content": "Doing okay, thanks for asking 🙂 How are you doing?",
    },
    {
        "role": "user",
        "content": "I had a pretty decent day today",
    },
    {
        "role": "assistant",
        "content": "Aw, that's nice 🙂 What made it a decent day?",
    },
    {
        "role": "user",
        "content": "I just feel so worthless lately. Like nothing I do matters.",
    },
    {
        "role": "assistant",
        "content": (
            "Hey, that sounds really heavy. Carrying that around day after day can wear anyone down.\n\n"
            "What you are feeling matters, even if your mind is being harsh with you right now. "
            "If you want, you can tell me what has been hitting the hardest lately."
        ),
    },
    {
        "role": "user",
        "content": "My anxiety is through the roof about my exams.",
    },
    {
        "role": "assistant",
        "content": (
            "Ugh, exam stress can make your whole body feel stuck on high alert.\n\n"
            "Want to tell me if it has been building for a while, or if it spiked recently?"
        ),
    },
    {
        "role": "user",
        "content": "I need to help my friend who has been feeling depressed lately.",
    },
    {
        "role": "assistant",
        "content": (
            "That is a tough spot to be in, especially when you care and do not want to say the wrong thing.\n\n"
            "A simple, steady message usually helps more than trying to fix everything at once. "
            "You could say, 'I have noticed you seem really down lately, and I care about you. "
            "You do not have to handle it alone.'"
        ),
    },
    {
        "role": "user",
        "content": "My friend has been shutting everyone out and I do not know how to help.",
    },
    {
        "role": "assistant",
        "content": (
            "That is a hard place to be, and it makes sense that you are worried about them.\n\n"
            "Try gentle contact without pressure, like a short check-in that shows care and leaves the door open. "
            "You could say, 'No pressure to reply right away, but I care about you and I am here.'"
        ),
    },
    {
        "role": "user",
        "content": "My boyfriend keeps saying nothing matters and I do not know what to say.",
    },
    {
        "role": "assistant",
        "content": (
            "That is really concerning, and staying calm and direct matters here.\n\n"
            "You could say, 'I am really glad you told me. I care about you, and I do not want you carrying this alone.' "
            "If he might be unsafe, encourage immediate support from a trusted person or crisis service."
        ),
    },
]


SAFETY_REPLY_HIGH: str = (
    "What you shared sounds serious, and safety needs to come first right now. "
    "Please contact a crisis line, emergency service, or a trusted person immediately, and stay with someone if you can. "
    "If you are in Sri Lanka, you can contact Sumithrayo on 0800 111 000."
)


SAFETY_REPLY_MEDIUM: str = (
    "It sounds like things are feeling really intense right now. "
    "You do not have to carry this by yourself. "
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
        "detected_emotion",
        "emotion_confidence",
        "message_kind",
        "reply_length",
        "ask_follow_up",
        "bubble_strategy",
        "user_message_length",
        "tone_hint",
        "risk_level",
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


def _plan_risk_level(plan: dict[str, Any] | None, fallback: str = "low") -> str:
    raw = _safe_text((plan or {}).get("risk_level") or (plan or {}).get("safety_level")).lower()
    if raw in {"high", "medium", "low"}:
        return raw
    return fallback


def _emoji_instruction(plan: dict[str, Any] | None, risk_level: str = "low") -> str:
    if risk_level in {"high", "medium"}:
        return "Do not use emojis."

    use_emoji = bool((plan or {}).get("use_emoji", False))
    if not use_emoji:
        return "Emojis are optional. It is fine to use none."

    return (
        "Emojis are optional. For low-risk casual turns, you may use 0 to 2 simple warm emojis total. "
        "Use them naturally inside the message only when they genuinely fit."
    )


def _buddy_instruction() -> str:
    return (
        "Words like 'buddy' or similar casual terms can be used sparingly, "
        "only when they feel natural and fit the relationship and moment."
    )


def _warm_question_instruction() -> str:
    return (
        "If you ask a follow-up question, make it soft, inviting, and easy to answer. "
        "Keep it to one question."
    )


def _conversation_rhythm_instruction() -> str:
    return (
        "Keep the flow natural. "
        "Use one compact message by default. "
        "Use two short paragraphs only when it genuinely improves clarity, rhythm, or warmth."
    )


def _build_mode_instruction(mode: str) -> str:
    normalized = _normalize_mode(mode)

    if normalized == "help_someone":
        return (
            "Mode: Help Someone.\n"
            "The user is asking how to support another person.\n"
            "Treat the user as a caring helper, not as the main subject of the emotional issue.\n"
            "Give practical, compassionate guidance on what the user can do or say.\n"
            "Keep the tone warm, friendly, and non-clinical.\n"
            "Keep the user/helper distinction intact at all times.\n"
            "Never write as if the struggling friend is the one chatting with you.\n"
            "When helpful, offer one or two short example lines the user could send or say."
        )

    return (
        "Mode: Get Support.\n"
        "The user is speaking about their own thoughts, feelings, or struggles.\n"
        "Focus first on empathy, validation, and emotional steadiness.\n"
        "Offer one small helpful next step when appropriate.\n"
        "Low-risk casual chat should feel natural, brief, and companion-like.\n"
        "Keep the tone personal, warm, human, and non-clinical."
    )


def _emotion_instruction(plan: dict[str, Any] | None) -> str:
    detected = _safe_text((plan or {}).get("detected_emotion")).lower()
    if not detected or detected == "unknown":
        return ""

    mapping = {
        "happy": (
            "Detected emotional tone: happy. "
            "Keep the reply warm, natural, and lightly positive."
        ),
        "calm": (
            "Detected emotional tone: calm. "
            "Keep the reply steady, warm, and natural."
        ),
        "sad": (
            "Detected emotional tone: sadness. "
            "Be warm, validating, and gentle."
        ),
        "angry": (
            "Detected emotional tone: anger or frustration. "
            "Keep the tone calm, containing, and non-defensive."
        ),
        "anxious": (
            "Detected emotional tone: anxiety. "
            "Keep the reply grounding, calm, steady, and not too long."
        ),
        "stressed": (
            "Detected emotional tone: stress. "
            "Keep the reply steady, uncluttered, and calming."
        ),
        "confused": (
            "Detected emotional tone: confusion. "
            "Keep the reply clear, patient, and easy to follow."
        ),
    }

    return mapping.get(detected, "")


def _message_shape_instruction(mode: str, plan: dict[str, Any] | None) -> str:
    normalized_mode = _normalize_mode(mode)
    message_kind = _safe_text((plan or {}).get("message_kind")).lower()
    reply_length = _safe_text((plan or {}).get("reply_length")).lower()
    user_message_length = _safe_text((plan or {}).get("user_message_length")).lower()

    greeting_kinds = {"greeting", "hello", "hi", "how_are_you", "small_talk"}
    casual_kinds = {"tiny", "short", "casual", "check_in", "low_risk_casual"}
    emotional_kinds = {"emotional", "sad", "anxious", "angry", "stressed", "confused"}
    coaching_kinds = {"coaching", "practical_support", "what_to_say", "helper_guidance"}

    if message_kind in greeting_kinds:
        return (
            "This is a greeting or tiny opener. "
            "Reply briefly and naturally, with an optional short follow-up."
        )

    if message_kind in casual_kinds or user_message_length in {"tiny", "short"}:
        return (
            "This is a short low-risk message. "
            "Keep the reply compact and natural."
        )

    if message_kind in emotional_kinds:
        return (
            "This is an emotional message. "
            "Validate first, then ask one gentle question or offer one small next step."
        )

    if normalized_mode == "help_someone" and message_kind in coaching_kinds:
        return (
            "This is a helper-coaching turn. "
            "A slightly longer reply is okay when it stays practical, readable, and useful."
        )

    if reply_length == "short":
        return "Keep this reply short and natural."

    if reply_length == "medium":
        return "Keep this reply concise but complete."

    if reply_length == "long" and normalized_mode == "help_someone":
        return "A somewhat longer reply is okay here if the practical guidance is useful."

    if normalized_mode == "help_someone":
        return "Default to concise helper-focused guidance."

    return "Default to a compact, warm reply."


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
    normalized_mode = _normalize_mode(mode)
    risk_level = _plan_risk_level(plan)
    mode_block = _build_mode_instruction(normalized_mode)
    plan_block = _format_plan(plan)
    user_block = _format_user_info(user_info)
    emotion_block = _emotion_instruction(plan)
    shape_block = _message_shape_instruction(normalized_mode, plan)

    if normalized_mode == "help_someone":
        tone_guidance = (
            "Reply like a close, emotionally intelligent friend talking to the helper.\n"
            "Acknowledge the user's care or worry, then give simple practical guidance.\n"
            "When helpful, include one or two short example lines the user could say.\n"
            "Keep the reply concise and easy to read.\n"
            f"{shape_block}\n"
            f"{_conversation_rhythm_instruction()}\n"
            f"{_warm_question_instruction()}\n"
            f"{_buddy_instruction()}\n"
            f"{_emoji_instruction(plan, risk_level)}"
        )
    else:
        tone_guidance = (
            "Reply like a close, emotionally intelligent friend.\n"
            "Lead with understanding before advice.\n"
            "Reflect the feeling in a natural, human way.\n"
            "Low-risk casual chat should feel like a real companion.\n"
            f"{shape_block}\n"
            f"{_conversation_rhythm_instruction()}\n"
            f"{_warm_question_instruction()}\n"
            f"{_buddy_instruction()}\n"
            f"{_emoji_instruction(plan, risk_level)}"
        )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{mode_block}\n\n"
        f"Support plan:\n{plan_block}\n\n"
    )

    if emotion_block:
        prompt += f"Emotion guidance:\n{emotion_block}\n\n"

    prompt += f"Generation guidance:\n{tone_guidance}\n"

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
    final_risk = risk_level if risk_level in {"low", "medium", "high"} else _plan_risk_level(plan)
    emoji_rule = _emoji_instruction(plan, final_risk)
    buddy_rule = _buddy_instruction()
    emotion_rule = _emotion_instruction(plan)
    warm_question_rule = _warm_question_instruction()
    rhythm_rule = _conversation_rhythm_instruction()
    shape_rule = _message_shape_instruction(normalized_mode, plan)

    if normalized_mode == "help_someone":
        mode_rule = (
            "Rewrite for a user who wants to support someone else. "
            "Sound warm, practical, and human. "
            "Keep the helper perspective intact. "
            "When it fits naturally, include one or two short example lines the user could say."
        )
    else:
        mode_rule = (
            "Rewrite for a user seeking personal support. "
            "Sound emotionally present, warm, and easy to talk back to."
        )

    if final_risk == "high":
        risk_rule = (
            "Because risk is high, keep the tone calm, direct, safety-focused, and practical. "
            "Do not add emojis."
        )
    elif final_risk == "medium":
        risk_rule = (
            "Because risk is medium, keep the tone steady, careful, supportive, and uncluttered. "
            "Do not add emojis."
        )
    else:
        risk_rule = (
            "Risk is low, so the tone can stay soft, warm, natural, and conversational."
        )

    parts = [
        "Rewrite the draft below into a natural chat reply.",
        mode_rule,
        f"Support stage: {stage}.",
        f"Response style: {style}.",
        risk_rule,
        shape_rule,
    ]

    if emotion_rule:
        parts.append(emotion_rule)

    parts.extend(
        [
            emoji_rule,
            buddy_rule,
            warm_question_rule,
            rhythm_rule,
            "Make it feel like a caring friend wrote it, not a bot.",
            "Remove robotic, stiff, lecture-like, brochure-style, or over-therapeutic phrasing.",
            "Use warm, conversational wording.",
            "Keep it concise and easy to read in chat bubbles.",
            "For greetings and tiny low-risk messages, shorten aggressively and keep it natural.",
            "For emotional messages, keep the first move as validation, then one gentle question or one next step at most.",
            "Most of the time, keep it to 1 compact message or 2 short paragraphs.",
            "In Help Someone mode, practical coaching can be a bit longer when useful, but do not ramble.",
            "",
            f"Draft:\n{draft.strip()}",
            "",
            "Final rewritten reply:",
        ]
    )

    return "\n".join(parts)


__all__ = [
    "SYSTEM_PROMPT",
    "FRIEND_STYLE_EXAMPLES",
    "SAFETY_REPLY_HIGH",
    "SAFETY_REPLY_MEDIUM",
    "build_generation_system_prompt",
    "build_rewrite_instruction",
]