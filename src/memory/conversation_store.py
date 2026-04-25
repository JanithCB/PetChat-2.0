"""
src/memory/conversation_store.py -- Minimal Supabase-backed conversation store.

Public API
----------
save_message(user_id, session_id, role, content, meta=None) -> None
load_recent_history(user_id, session_id, limit=None) -> list[dict[str, str]]

Notes
-----
- No schema creation is done here.
- If Supabase is disabled or unavailable, functions degrade gracefully.
- Returned history is in prompt-friendly role/content format.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import MAX_HISTORY_TURNS
from src.memory.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def save_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Save one message row to Supabase if available.

    Expected table columns:
    - user_id
    - session_id
    - role
    - content
    - meta
    """
    sb = get_supabase()
    if sb is None:
        return

    clean_role = (role or "").strip()
    clean_content = (content or "").strip()

    if clean_role not in {"user", "assistant", "system"}:
        logger.warning("Skipping save_message with invalid role: %r", role)
        return

    if not clean_content:
        return

    payload: dict[str, Any] = {
        "user_id": (user_id or "").strip(),
        "session_id": (session_id or "").strip(),
        "role": clean_role,
        "content": clean_content,
        "meta": meta or {},
    }

    try:
        sb.table("messages").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_message failed: %s", exc)


def load_recent_history(
    user_id: str,
    session_id: str,
    limit: int | None = None,
) -> list[dict[str, str]]:
    """
    Load recent messages for one user/session in oldest-first order.

    Returns:
        [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
        ]
    """
    sb = get_supabase()
    if sb is None:
        return []

    effective_limit = limit or (MAX_HISTORY_TURNS * 2)

    try:
        response = (
            sb.table("messages")
            .select("role, content")
            .eq("user_id", (user_id or "").strip())
            .eq("session_id", (session_id or "").strip())
            .order("created_at", desc=True)
            .limit(effective_limit)
            .execute()
        )

        rows = response.data or []
        rows.reverse()

        history: list[dict[str, str]] = []
        for row in rows:
            role = str(row.get("role", "")).strip()
            content = str(row.get("content", "")).strip()

            if role not in {"user", "assistant", "system"}:
                continue
            if not content:
                continue

            history.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        return history

    except Exception as exc:  # noqa: BLE001
        logger.warning("load_recent_history failed: %s", exc)
        return []