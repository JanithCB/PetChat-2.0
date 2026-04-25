"""
src/memory/supabase_client.py -- Minimal lazy Supabase client for PetChat-2.0.

Public API
----------
get_supabase() -> Client | None

Behavior
--------
- Returns a singleton client when Supabase is enabled and configured.
- Returns None when disabled, misconfigured, or the dependency is missing.
- Does not create schemas or tables.
- Never logs the full service key.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client


logger = logging.getLogger(__name__)

_client: "Client | None" = None
_init_attempted: bool = False


def get_supabase() -> "Client | None":
    """
    Return a singleton Supabase client or None if unavailable.
    """
    global _client, _init_attempted

    if _init_attempted:
        return _client

    _init_attempted = True
    _client = _create_client()
    return _client


def reset_supabase_client() -> None:
    """
    Reset singleton state. Useful for tests or manual re-init flows.
    """
    global _client, _init_attempted
    _client = None
    _init_attempted = False


def _create_client() -> "Client | None":
    try:
        from src.config import USE_SUPABASE_MEMORY, SUPABASE_SERVICE_KEY, SUPABASE_URL
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load Supabase config: %s", exc)
        return None

    if not USE_SUPABASE_MEMORY:
        logger.debug("Supabase memory is disabled in config.")
        return None

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.warning(
            "Supabase is not fully configured (url set=%s, service_key set=%s). Memory is disabled.",
            bool(SUPABASE_URL),
            bool(SUPABASE_SERVICE_KEY),
        )
        return None

    try:
        from supabase import create_client  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "supabase package is not installed. Memory is disabled."
        )
        return None

    try:
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info(
            "Supabase client initialized for %s",
            _safe_url_for_logs(SUPABASE_URL),
        )
        return client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialize Supabase client: %s", exc)
        return None


def _safe_url_for_logs(url: str) -> str:
    """
    Return a shortened URL safe for logs.
    """
    text = (url or "").strip()
    if not text:
        return "<empty>"
    if len(text) <= 40:
        return text
    return f"{text[:40]}..."