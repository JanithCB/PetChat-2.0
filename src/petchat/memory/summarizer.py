"""
memory/summarizer.py — Long-term memory summariser for PetChat-2.0.

Builds or updates a short narrative summary of a user's recent conversations
by calling the LLM through the same provider abstraction the pipeline uses.

Public API
----------
build_user_summary(provider, user_messages, existing_summary) -> str
    Returns a 1-2 paragraph summary string, or the existing summary on failure.

Design rules
------------
- No safety decisions here; purely extractive summarisation.
- Prompt instructs the model to focus on:
    recurring emotional themes, coping patterns, key stressors, and
    overall stability trend — not to diagnose or judge.
- The result is stored by the caller via conversation_store.upsert_user_summary().
- Falls back to existing_summary (or "") on any provider error so the
  pipeline is never blocked.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider protocol (mirrors providers.BaseProvider)
# ---------------------------------------------------------------------------

class _ChatProvider(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        ...


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SUMMARISER_SYSTEM = """You are a quiet, reflective assistant helping a supportive chatbot understand a user better over time.

Your task is to write a concise, warm summary of what has been going on for this user based on the conversation excerpts provided. Focus on:
- Recurring emotional themes (e.g. anxiety, loneliness, stress at work)
- Key life stressors or problems they have mentioned
- Emotional stability trends (improving, worsening, fluctuating)
- Any coping strategies or sources of support they have referenced

Rules:
- Write 1 to 2 short paragraphs in plain prose.
- Do not diagnose or label the user with clinical terms.
- Do not mention that you are summarising or that this is a memory system.
- Do not include specific quotes; only themes and patterns.
- Keep each paragraph under 80 words.
- Use past tense and third-person perspective (e.g. "The user has been…").
- If no meaningful pattern is present yet, write a single honest sentence.
"""

_UPDATE_INSTRUCTION = """An existing summary is provided below. Integrate it with the new conversation excerpts. Keep the final result to 1-2 paragraphs. Retain important historical patterns but update or drop details made irrelevant by new context.

Existing summary:
{existing}
"""

_USER_PROMPT_TEMPLATE = """Recent user messages (oldest to newest):
{messages}

{update_block}
Write the updated summary now:
"""

# Max characters from each user message included in the prompt.
_MAX_MSG_CHARS: int = 300

# Hard cap on total message block to keep prompt within context window.
_MAX_BLOCK_CHARS: int = 4_000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_user_summary(
    provider:          "_ChatProvider",
    user_messages:     list[str],
    existing_summary:  str | None = None,
) -> str:
    """
    Summarise the user's recent messages into 1-2 paragraphs.

    Parameters
    ----------
    provider        : Any object with a .chat(messages) -> str method.
    user_messages   : Chronological list of raw user message strings.
    existing_summary: Previous summary text to update, or None for first run.

    Returns
    -------
    A plain-text summary string.
    Falls back to existing_summary (or "") on LLM error.
    """
    if not user_messages:
        logger.debug("build_user_summary called with no messages.")
        return existing_summary or ""

    message_block = _build_message_block(user_messages)
    update_block  = _build_update_block(existing_summary)
    user_prompt   = _USER_PROMPT_TEMPLATE.format(
        messages=message_block,
        update_block=update_block,
    ).strip()

    messages: list[dict[str, str]] = [
        {"role": "system",  "content": _SUMMARISER_SYSTEM},
        {"role": "user",    "content": user_prompt},
    ]

    try:
        result = provider.chat(messages, temperature=0.3, max_tokens=300)
        result = result.strip()
        if not result:
            raise ValueError("Provider returned empty summary.")
        logger.debug("Summary generated (%d chars).", len(result))
        return result

    except Exception as exc:  # noqa: BLE001
        logger.warning("build_user_summary failed: %s — keeping existing.", exc)
        return existing_summary or ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_message_block(user_messages: list[str]) -> str:
    lines: list[str] = []
    total: int = 0

    candidates: list[str] = []
    for msg in reversed(user_messages):
        snippet = msg.strip()[:_MAX_MSG_CHARS]
        if not snippet:
            continue
        size = len(snippet) + 6
        if total + size > _MAX_BLOCK_CHARS and candidates:
            break
        candidates.append(snippet)
        total += size

    candidates.reverse()

    for i, snippet in enumerate(candidates, start=1):
        lines.append(f"{i}. {snippet}")

    return "\n".join(lines) or "(no messages)"


def _build_update_block(existing_summary: str | None) -> str:
    """Return the existing-summary block or an empty string."""
    if not existing_summary or not existing_summary.strip():
        return ""
    return _UPDATE_INSTRUCTION.format(existing=existing_summary.strip())
