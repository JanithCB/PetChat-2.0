"""
memory/supabase_client.py — Lazy Supabase client singleton for PetChat-2.0.

Exposes
-------
get_supabase() -> supabase.Client | None
    Returns a live client when credentials are configured, otherwise None.

Design rules
------------
- No crash on missing deps or missing env-vars.
- One client is created per process (lazy singleton).
- A clear warning is emitted once when the client cannot be created so
  operators know why memory features are silently disabled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client  # pragma: no cover

from petchat.config import SUPABASE_ENABLED, SUPABASE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_client: "Client | None" = None
_init_attempted: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_supabase() -> "Client | None":
    """
    Return a ready Supabase client, or None when unavailable.

    Reasons it may return None:
    - SUPABASE_ENABLED is False in config.
    - SUPABASE_URL or SUPABASE_KEY are empty / not set.
    - The ``supabase`` Python package is not installed.
    - The initial connection attempt raised an exception.

    The warning is emitted only once per process.
    """
    global _client, _init_attempted

    if _init_attempted:
        return _client

    _init_attempted = True
    _client = _try_create_client()
    return _client


def reset_client() -> None:
    """
    Force the next get_supabase() call to reattempt client creation.
    Primarily useful in tests.
    """
    global _client, _init_attempted
    _client = None
    _init_attempted = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _try_create_client() -> "Client | None":
    if not SUPABASE_ENABLED:
        logger.debug("Supabase is disabled in config — memory features off.")
        return None

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning(
            "Supabase credentials missing (SUPABASE_URL=%r, SUPABASE_KEY set=%s). "
            "Long-term memory is disabled.",
            SUPABASE_URL or "",
            bool(SUPABASE_KEY),
        )
        return None

    try:
        from supabase import create_client  # noqa: PLC0415

        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client ready (url=%s…).", SUPABASE_URL[:30])
        return client

    except ImportError:
        logger.warning(
            "supabase package not installed — run `pip install supabase`. "
            "Long-term memory is disabled."
        )
        return None

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not create Supabase client: %s. Long-term memory is disabled.",
            exc,
        )
        return None
