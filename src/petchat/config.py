"""
config.py -- Central configuration for PetChat-2.0.

All secrets are loaded from environment variables / .env file.
Import-safe: no side effects beyond reading os.environ and creating
the required runtime directories.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PACKAGE_ROOT: Path = Path(__file__).resolve().parent        # src/petchat/
_PROJECT_ROOT: Path = _PACKAGE_ROOT.parent.parent            # project root

# RAG docs: override via env var so users can point at cleaned_txt/ easily
RAG_DOCS_DIR: Path = Path(
    os.environ.get("RAG_DOCS_DIR", str(_PROJECT_ROOT / "cleaned_txt"))
)
RAG_CACHE_DIR: Path = Path(
    os.environ.get("RAG_CACHE_DIR", str(_PROJECT_ROOT / "data" / "rag_cache"))
)
LOG_DIR:  Path = _PROJECT_ROOT / "data" / "logs"
LOG_FILE: Path = LOG_DIR / "petchat.log"

EVAL_PROMPTS_FILE: Path = _PROJECT_ROOT / "src" / "petchat" / "eval" / "eval_prompts.json"

# Ensure runtime directories exist at import time.
for _dir in (RAG_CACHE_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Conversation window
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS: int = 8

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

# Set USE_SUPABASE_MEMORY=0 in .env to run fully offline.
USE_SUPABASE_MEMORY: bool = os.environ.get("USE_SUPABASE_MEMORY", "0") not in (
    "0", "false", "False"
)
# Alias expected by supabase_client.py
SUPABASE_ENABLED: bool = USE_SUPABASE_MEMORY

ENABLE_CLOUD_MODELS: bool = os.environ.get("ENABLE_CLOUD_MODELS", "1") not in (
    "0", "false", "False"
)
ENABLE_LOCAL_MODELS: bool = os.environ.get("ENABLE_LOCAL_MODELS", "1") not in (
    "0", "false", "False"
)

# Set RAG_ENABLED=0 to disable RAG at runtime without removing docs.
RAG_ENABLED: bool = os.environ.get("RAG_ENABLED", "1") not in (
    "0", "false", "False"
)

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")

# ---------------------------------------------------------------------------
# Cloud providers
# ---------------------------------------------------------------------------

CLOUD_PROVIDERS: dict[str, str] = {
    "llama_scout": "meta-llama/llama-4-scout-17b-16e-instruct",
    "secondary":   "gemini-2.0-flash",
}

DEFAULT_CLOUD_PROVIDER: str = "llama_scout"

GROQ_API_KEY:   str = os.environ.get("GROQ_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")

# ---------------------------------------------------------------------------
# Local providers (Ollama)
# ---------------------------------------------------------------------------

LOCAL_PROVIDERS: dict[str, str] = {
    "llama3_2_3b": "llama3.2:3b",          # what you have installed right now
    "llama3_8b":   "llama3:8b-instruct",
    "mistral_7b":  "mistral:7b-instruct",
}

DEFAULT_LOCAL_PROVIDER: str = "llama3_2_3b"

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Embed model used by the RAG engine (must be pulled in Ollama)
RAG_EMBED_MODEL: str = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")

# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------

THEME_COLORS: dict[str, str] = {
    "background":       "#000000",
    "accent":           "#FFD54A",
    "user_bubble":      "#FFD54A",
    "user_bubble_text": "#000000",
    "bot_bubble":       "#1A1A1A",
    "bot_bubble_text":  "#F0F0F0",
    "input_bg":         "#111111",
    "input_text":       "#F0F0F0",
    "status_text":      "#888888",
    "divider":          "#222222",
}

APP_NAME:    str = "PetChat"
APP_VERSION: str = "2.0.0"

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class SupabaseConfig(TypedDict):
    url:        str
    key:        str
    use_memory: bool


class ModelEntry(TypedDict):
    provider_id: str
    model_id:    str
    is_local:    bool


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_supabase_config() -> SupabaseConfig:
    """Return Supabase connection details and the memory feature flag."""
    return SupabaseConfig(
        url=SUPABASE_URL,
        key=SUPABASE_KEY,
        use_memory=USE_SUPABASE_MEMORY,
    )


def get_default_models() -> dict[str, "ModelEntry | None"]:
    """
    Return the currently active default cloud and local model entries.
    Values are None when the respective provider group is disabled.
    """
    cloud: ModelEntry | None = None
    local: ModelEntry | None = None

    if ENABLE_CLOUD_MODELS:
        cloud = ModelEntry(
            provider_id=DEFAULT_CLOUD_PROVIDER,
            model_id=CLOUD_PROVIDERS[DEFAULT_CLOUD_PROVIDER],
            is_local=False,
        )

    if ENABLE_LOCAL_MODELS:
        local = ModelEntry(
            provider_id=DEFAULT_LOCAL_PROVIDER,
            model_id=LOCAL_PROVIDERS[DEFAULT_LOCAL_PROVIDER],
            is_local=True,
        )

    return {"cloud": cloud, "local": local}


def get_all_models() -> list[ModelEntry]:
    """
    Return a flat list of every enabled model entry.
    Used to populate the model-selection dropdown in the UI.
    """
    models: list[ModelEntry] = []

    if ENABLE_CLOUD_MODELS:
        for pid, mid in CLOUD_PROVIDERS.items():
            models.append(ModelEntry(provider_id=pid, model_id=mid, is_local=False))

    if ENABLE_LOCAL_MODELS:
        for pid, mid in LOCAL_PROVIDERS.items():
            models.append(ModelEntry(provider_id=pid, model_id=mid, is_local=True))

    return models


def get_model_by_provider_id(provider_id: str) -> ModelEntry:
    """
    Look up a ModelEntry by its stable provider_id string.
    Raises KeyError if the provider_id is unknown.
    """
    if provider_id in CLOUD_PROVIDERS:
        return ModelEntry(
            provider_id=provider_id,
            model_id=CLOUD_PROVIDERS[provider_id],
            is_local=False,
        )
    if provider_id in LOCAL_PROVIDERS:
        return ModelEntry(
            provider_id=provider_id,
            model_id=LOCAL_PROVIDERS[provider_id],
            is_local=True,
        )
    raise KeyError(f"Unknown provider_id: {provider_id!r}")
