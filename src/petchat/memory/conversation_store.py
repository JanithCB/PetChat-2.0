"""
memory/conversation_store.py — Supabase-backed conversation memory for PetChat-2.0.

Schema assumed (create once in Supabase dashboard / migrations):
------------------------------------------------------------------------
users            (id UUID PK default gen_random_uuid(),
                  username TEXT UNIQUE NOT NULL,
                  full_name TEXT,
                  created_at TIMESTAMPTZ default now())

sessions         (id UUID PK default gen_random_uuid(),
                  user_id UUID REFERENCES users(id),
                  title TEXT,
                  started_at TIMESTAMPTZ default now(),
                  ended_at TIMESTAMPTZ)

messages         (id UUID PK default gen_random_uuid(),
                  session_id UUID REFERENCES sessions(id),
                  role TEXT NOT NULL,          -- "user" | "assistant"
                  content TEXT NOT NULL,
                  risk_level TEXT,
                  primary_emotion TEXT,
                  problem_hint TEXT,
                  support_stage TEXT,
                  response_style TEXT,
                  emoji_used TEXT,
                  meta JSONB,
                  created_at TIMESTAMPTZ default now())

user_summaries   (user_id UUID PRIMARY KEY REFERENCES users(id),
                  summary TEXT NOT NULL,
                  updated_at TIMESTAMPTZ default now())
------------------------------------------------------------------------

All public functions degrade gracefully when Supabase is unavailable:
- ensure_user / start_session return a deterministic fallback ID so the
  pipeline can always pass a session_id without branching.
- save_turn / load_* silently no-op or return empty defaults.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from petchat.memory.supabase_client import get_supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback ID helpers (used when Supabase is off)
# ---------------------------------------------------------------------------

def _offline_uuid(seed: str) -> str:
    """Deterministic pseudo-UUID from a string seed — never clashes with real UUIDs."""
    digest = hashlib.sha1(seed.encode()).hexdigest()  # noqa: S324
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def ensure_user(username: str, full_name: str | None = None) -> str:
    """
    Return the Supabase user_id for username, creating the row if needed.

    Returns a deterministic fallback UUID when Supabase is unavailable.
    """
    sb = get_supabase()
    if sb is None:
        return _offline_uuid(f"user:{username}")

    try:
        result = (
            sb.table("users")
            .select("id")
            .eq("username", username)
            .maybe_single()
            .execute()
        )
        if result.data:
            return result.data["id"]

        payload: dict[str, Any] = {"username": username}
        if full_name:
            payload["full_name"] = full_name

        insert_result = sb.table("users").insert(payload).execute()
        return insert_result.data[0]["id"]

    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_user failed: %s", exc)
        return _offline_uuid(f"user:{username}")


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def start_session(user_id: str, title: str | None = None) -> str:
    """
    Create a new session row and return its UUID.

    Returns a time-based fallback UUID when Supabase is unavailable.
    """
    sb = get_supabase()
    ts = datetime.now(timezone.utc).isoformat()

    if sb is None:
        return _offline_uuid(f"session:{user_id}:{ts}")

    try:
        payload: dict[str, Any] = {
            "user_id":    user_id,
            "started_at": ts,
        }
        if title:
            payload["title"] = title

        result = sb.table("sessions").insert(payload).execute()
        return result.data[0]["id"]

    except Exception as exc:  # noqa: BLE001
        logger.warning("start_session failed: %s", exc)
        return _offline_uuid(f"session:{user_id}:{ts}")


def end_session(session_id: str) -> None:
    """Stamp ended_at on the session row."""
    sb = get_supabase()
    if sb is None:
        return

    try:
        (
            sb.table("sessions")
            .update({"ended_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", session_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("end_session failed: %s", exc)


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------

def save_turn(
    session_id:     str,
    role:           str,
    content:        str,
    risk_level:     str       = "low",
    primary_emotion: str      = "",
    problem_hint:   str       = "",
    support_stage:  str       = "",
    response_style: str       = "",
    emoji_used:     str       = "",
    meta:           dict | None = None,
) -> None:
    """
    Persist one conversation turn.  No-ops gracefully when Supabase is off.
    """
    sb = get_supabase()
    if sb is None:
        return

    payload: dict[str, Any] = {
        "session_id":     session_id,
        "role":           role,
        "content":        content,
        "risk_level":     risk_level,
        "primary_emotion": primary_emotion,
        "problem_hint":   problem_hint,
        "support_stage":  support_stage,
        "response_style": response_style,
        "emoji_used":     emoji_used,
        "created_at":     datetime.now(timezone.utc).isoformat(),
    }
    if meta:
        payload["meta"] = json.dumps(meta)

    try:
        sb.table("messages").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_turn failed: %s", exc)


# ---------------------------------------------------------------------------
# Memory retrieval
# ---------------------------------------------------------------------------

def load_recent_turns(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Return the most recent `limit` messages for this user across all sessions.

    Columns returned: role, content, risk_level, primary_emotion,
                      problem_hint, support_stage, created_at.

    Returns [] when Supabase is off or the query fails.
    """
    sb = get_supabase()
    if sb is None:
        return []

    try:
        # Join messages -> sessions -> user_id filter via a Postgres view
        # or fall back to two-step query (no RPC required).
        sessions_result = (
            sb.table("sessions")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        session_ids: list[str] = [row["id"] for row in (sessions_result.data or [])]
        if not session_ids:
            return []

        messages_result = (
            sb.table("messages")
            .select(
                "role, content, risk_level, primary_emotion, "
                "problem_hint, support_stage, created_at"
            )
            .in_("session_id", session_ids)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows: list[dict[str, Any]] = messages_result.data or []
        rows.reverse()   # oldest first for prompt building
        return rows

    except Exception as exc:  # noqa: BLE001
        logger.warning("load_recent_turns failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# User summary (long-term compressed memory)
# ---------------------------------------------------------------------------

def load_user_summary(user_id: str) -> str | None:
    """
    Return the compressed long-term summary for this user, or None.

    The summary is written by the eval / summariser module (not this file).
    """
    sb = get_supabase()
    if sb is None:
        return None

    try:
        result = (
            sb.table("user_summaries")
            .select("summary")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data["summary"] if result.data else None

    except Exception as exc:  # noqa: BLE001
        logger.warning("load_user_summary failed: %s", exc)
        return None


def upsert_user_summary(user_id: str, summary_text: str) -> None:
    """
    Create or overwrite the user's long-term summary.

    Uses Supabase upsert (INSERT … ON CONFLICT DO UPDATE).
    No-ops gracefully when Supabase is off.
    """
    sb = get_supabase()
    if sb is None:
        return

    try:
        (
            sb.table("user_summaries")
            .upsert(
                {
                    "user_id":    user_id,
                    "summary":    summary_text,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="user_id",
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("upsert_user_summary failed: %s", exc)
