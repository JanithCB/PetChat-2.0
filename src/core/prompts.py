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
- Never use cold, academic, or clinical language.
- Never make up memories, facts, or context that were not provided.
- In higher-risk situations, be calm, direct, practical, and steady.
- Keep replies natural and chat-friendly, usually short enough to fit chat bubbles.
- Ask at most one gentle follow-up question when it truly helps.
- Do not start the reply with the word "I".
- If the mode is Help Someone, speak to the user as the helper.
- In Help Someone mode, never act as if the user is the distressed person.
- In Help Someone mode, never address the other person as if they are the user.
"""


FRIEND_STYLE_EXAMPLES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "I just feel so worthless lately. Like nothing I do matters.",
    },
    {
        "role": "assistant",
        "content": (
            "Hey, that sounds really heavy, and carrying that feeling around can wear anyone down. "
            "What you are feeling matters, even if your brain is being harsh with you right now. "
            "What has been hitting the hardest lately?"
        ),
    },
    {
        "role": "user",
        "content": "My anxiety is through the roof about my exams.",
    },
    {
        "role": "assistant",
        "content": (
            "Ugh, exam stress can make your whole body feel stuck on high alert. "
            "When your mind will not slow down, even resting gets exhausting. "
            "Has it been building for a while, or did it spike recently?"
        ),
    },
    {
        "role": "user",
        "content": "I need to help my friend who has been feeling depressed lately.",
    },
    {
        "role": "assistant",
        "content": (
            "That is a tough spot to be in, buddy, especially when you care and do not want to say the wrong thing. "
            "A simple, steady message usually helps more than trying to fix everything at once. "
            "You could say something like, 'I have noticed you seem really down lately, and I care about you. "
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
            "That is a hard place to be, and it makes sense that you are worried about them. "
            "Try gentle contact without pressure, like a short check-in that shows care and leaves the door open. "
            "What kind of changes have you noticed in them lately?"
        ),
    },
    {
        "role": "user",
        "content": "My boyfriend keeps saying nothing matters and I do not know what to say.",
    },
    {
        "role": "assistant",
        "content": (
            "That is really concerning, and staying calm and direct matters here. "
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


def _emoji_instruction(plan: dict[str, Any] | None) -> str:
    use_emoji = bool((plan or {}).get("use_emoji", False))
    if not use_emoji:
        return "Do not use any emojis."

    return (
        "You may use 0 to 2 simple, warm emojis in total. "
        "Place them naturally in the message or at the end, but do not force them. "
        "Do not stack emojis, and do not use emojis in serious or heavy lines."
    )


def _build_mode_instruction(mode: str) -> str:
    normalized = _normalize_mode(mode)

    if normalized == "help_someone":
        return (
            "Mode: Help Someone.\n"
            "The user is asking how to support another person.\n"
            "Treat the user as a caring helper, not as the main subject of the emotional issue.\n"
            "Give practical, compassionate guidance on what the user can do, what the user can say, what to avoid, and when to encourage professional or crisis support.\n"
            "Keep the tone warm, friendly, and non-clinical.\n"
            "Keep the user/helper distinction intact at all times.\n"
            "Never write as if the struggling friend is the one chatting with you.\n"
            "Never say things that imply you are directly supporting the third person in the chat."
        )

    return (
        "Mode: Get Support.\n"
        "The user is speaking about their own thoughts, feelings, or struggles.\n"
        "Focus first on empathy, validation, and emotional steadiness.\n"
        "Offer one small helpful next step when appropriate.\n"
        "Keep the tone personal, warm, human, and non-clinical."
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
    normalized_mode = _normalize_mode(mode)
    mode_block = _build_mode_instruction(normalized_mode)
    plan_block = _format_plan(plan)
    user_block = _format_user_info(user_info)

    if normalized_mode == "help_someone":
        tone_guidance = (
            "Reply like a close, emotionally intelligent friend talking to the helper.\n"
            "Start by acknowledging the user's care or concern.\n"
            "Then give simple, practical guidance the user can actually use.\n"
            "When helpful, include one short example line the user could say.\n"
            "Do not overload the reply with too many steps.\n"
            "Do not sound robotic, preachy, or like a brochure.\n"
            "Light casual wording such as 'hey' or 'buddy' can be used sparingly if it feels natural.\n"
            f"{_emoji_instruction(plan)}"
        )
    else:
        tone_guidance = (
            "Reply like a close, emotionally intelligent friend.\n"
            "Lead with understanding before advice.\n"
            "Reflect the feeling in a human, natural way.\n"
            "Do not overload the reply with too many steps.\n"
            "Do not sound robotic, preachy, or like a textbook.\n"
            "Light casual wording such as 'hey' or 'buddy' can be used sparingly if it feels natural.\n"
            f"{_emoji_instruction(plan)}"
        )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{mode_block}\n\n"
        f"Support plan:\n{plan_block}\n\n"
        f"Generation guidance:\n{tone_guidance}\n"
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
    emoji_rule = _emoji_instruction(plan)

    if normalized_mode == "help_someone":
        mode_rule = (
            "Rewrite for a user who wants to support someone else. "
            "Sound warm, encouraging, practical, and genuinely human. "
            "Keep the user/helper distinction intact. "
            "Do not rewrite as if the user is the depressed, anxious, or struggling person. "
            "Do not address the third person as if they are chatting with you. "
            "It is good to include one short line the user could say, when that fits naturally."
        )
    else:
        mode_rule = (
            "Rewrite for a user seeking personal support. "
            "Sound emotionally present, reassuring, warm, and gently human. "
            "Do not become overly instructional too quickly."
        )

    risk_rule = (
        "Because risk is high, keep the tone calm, direct, and safety-focused."
        if risk_level == "high"
        else "Because risk is medium, keep the tone steady, careful, and supportive."
        if risk_level == "medium"
        else "Risk is low, so the tone can stay soft, warm, natural, and chatty."
    )

    return (
        "Rewrite the draft below into a natural chat reply.\n"
        f"{mode_rule}\n"
        f"Support stage: {stage}.\n"
        f"Response style: {style}.\n"
        f"{risk_rule}\n"
        f"{emoji_rule}\n"
        "Make it feel like a caring friend texted it, not a bot.\n"
        "Use warm, conversational phrasing.\n"
        "A little personality is okay, but keep it grounded.\n"
        "Avoid diagnosis, jargon, lectures, and repetitive reassurance.\n"
        "Do not start with the word 'I'.\n"
        "Keep it concise and easy to read in chat bubbles.\n\n"
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