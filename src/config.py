"""
config.py -- Central configuration for PetChat-2.0 v2.

Loads environment variables, exposes project paths, provider settings,
feature flags, UI constants, and typed helpers used across the app.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------

_PACKAGE_ROOT: Path = Path(__file__).resolve().parent          # .../src
_PROJECT_ROOT: Path = _PACKAGE_ROOT.parent                     # project root

load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()


# ---------------------------------------------------------------------------
# Small env helpers
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAG_DOCS_DIR: Path = Path(
    os.environ.get("RAG_DOCS_DIR", str(_PROJECT_ROOT / "cleaned_txt"))
).expanduser()

RAG_CACHE_DIR: Path = Path(
    os.environ.get("RAG_CACHE_DIR", str(_PROJECT_ROOT / "data" / "rag_cache"))
).expanduser()

LOG_DIR: Path = Path(
    os.environ.get("LOG_DIR", str(_PROJECT_ROOT / "data" / "logs"))
).expanduser()

EMOTION_MODEL_DIR: Path = Path(
    os.environ.get(
        "EMOTION_MODEL_DIR",
        str(_PROJECT_ROOT / "emotion_classifier" / "models" / "emotion_model_v2"),
    )
).expanduser()

LOG_FILE: Path = LOG_DIR / "app.log"
EVAL_LOG_FILE: Path = LOG_DIR / "eval.log"
EVAL_PROMPTS_FILE: Path = _PACKAGE_ROOT / "eval" / "eval_prompts.json"

for _dir in (RAG_CACHE_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# App limits / feature flags
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS: int = int(os.environ.get("MAX_HISTORY_TURNS", "8"))

ENABLE_CLOUD_MODELS: bool = _env_flag("ENABLE_CLOUD_MODELS", True)
ENABLE_LOCAL_MODELS: bool = _env_flag("ENABLE_LOCAL_MODELS", True)

# Retrieval-Augmented Generation:
# Enables optional knowledge retrieval for guidance-heavy turns.
RAG_ENABLED: bool = _env_flag("RAG_ENABLED", True)

# Memory / Supabase:
# Enables optional persistent memory features.
USE_SUPABASE_MEMORY: bool = _env_flag("USE_SUPABASE_MEMORY", False)
SUPABASE_ENABLED: bool = USE_SUPABASE_MEMORY

# Emotion classifier:
# This should remain optional. If disabled, the pipeline should skip
# classifier inference and continue with the existing rule-based flow.
USE_EMOTION_CLASSIFIER: bool = _env_flag("USE_EMOTION_CLASSIFIER", True)


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


# ---------------------------------------------------------------------------
# Providers / models
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
RAG_EMBED_MODEL: str = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")

LOCAL_PROVIDERS: dict[str, str] = {
    "phi4_mini": "phi4-mini:latest",
    "llama3_2_3b": "llama3.2:3b",
}

DEFAULT_LOCAL_PROVIDER: str = os.environ.get("DEFAULT_LOCAL_PROVIDER", "phi4_mini")
if DEFAULT_LOCAL_PROVIDER not in LOCAL_PROVIDERS:
    DEFAULT_LOCAL_PROVIDER = "phi4_mini"

CLOUD_PROVIDERS: dict[str, str] = {
    "llama_scout": "meta-llama/llama-4-scout-17b-16e-instruct",
    "secondary": "gemini-2.0-flash",
    "custom_api": os.environ.get(
        "DEFAULT_CLOUD_MODEL",
        "meta-llama/llama-4-scout-17b-16e-instruct",
    ),
}

DEFAULT_CLOUD_PROVIDER: str = os.environ.get("DEFAULT_CLOUD_PROVIDER", "llama_scout")
if DEFAULT_CLOUD_PROVIDER not in CLOUD_PROVIDERS:
    DEFAULT_CLOUD_PROVIDER = "llama_scout"

DEFAULT_CLOUD_BASE_URL: str = os.environ.get(
    "DEFAULT_CLOUD_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")
DEFAULT_CLOUD_API_KEY: str = os.environ.get("DEFAULT_CLOUD_API_KEY", "").strip()


# ---------------------------------------------------------------------------
# UI / modes
# ---------------------------------------------------------------------------

APP_NAME: str = "PetChat"
APP_VERSION: str = "2.1.0"

MODE_GET_SUPPORT: str = "get_support"
MODE_HELP_SOMEONE: str = "help_someone"
AVAILABLE_MODES: tuple[str, str] = (MODE_GET_SUPPORT, MODE_HELP_SOMEONE)
DEFAULT_MODE: str = MODE_GET_SUPPORT

THEME_COLORS: dict[str, str] = {
    "background": "#000000",
    "surface": "#0E0E0E",
    "surface_alt": "#151515",
    "accent": "#FFD54A",
    "accent_hover": "#E6BF43",
    "text": "#F5F5F5",
    "muted_text": "#A8A8A8",
    "divider": "#242424",
    "user_bubble": "#FFD54A",
    "user_bubble_text": "#000000",
    "bot_bubble": "#1A1A1A",
    "bot_bubble_text": "#F0F0F0",
    "input_bg": "#101010",
    "input_text": "#F0F0F0",
    "status_text": "#8E8E8E",
    "danger": "#D96B6B",
}


# ---------------------------------------------------------------------------
# Typed helpers
# ---------------------------------------------------------------------------

class SupabaseConfig(TypedDict):
    url: str
    key: str
    enabled: bool


class ModelEntry(TypedDict, total=False):
    provider_id: str
    model_id: str
    provider_type: str
    is_local: bool
    base_url: str
    api_key: str
    display_name: str


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_supabase_config() -> SupabaseConfig:
    return SupabaseConfig(
        url=SUPABASE_URL,
        key=SUPABASE_SERVICE_KEY,
        enabled=USE_SUPABASE_MEMORY,
    )


def get_default_models() -> dict[str, ModelEntry | None]:
    cloud: ModelEntry | None = None
    local: ModelEntry | None = None

    if ENABLE_CLOUD_MODELS:
        cloud = ModelEntry(
            provider_id=DEFAULT_CLOUD_PROVIDER,
            model_id=CLOUD_PROVIDERS[DEFAULT_CLOUD_PROVIDER],
            provider_type="cloud",
            is_local=False,
            base_url=DEFAULT_CLOUD_BASE_URL,
            api_key=DEFAULT_CLOUD_API_KEY,
            display_name=f"Cloud · {CLOUD_PROVIDERS[DEFAULT_CLOUD_PROVIDER]}",
        )

    if ENABLE_LOCAL_MODELS:
        local = ModelEntry(
            provider_id=DEFAULT_LOCAL_PROVIDER,
            model_id=LOCAL_PROVIDERS[DEFAULT_LOCAL_PROVIDER],
            provider_type="local",
            is_local=True,
            display_name=f"Local · {LOCAL_PROVIDERS[DEFAULT_LOCAL_PROVIDER]}",
        )

    return {"cloud": cloud, "local": local}


def get_all_models() -> list[ModelEntry]:
    models: list[ModelEntry] = []

    if ENABLE_LOCAL_MODELS:
        for provider_id, model_id in LOCAL_PROVIDERS.items():
            models.append(
                ModelEntry(
                    provider_id=provider_id,
                    model_id=model_id,
                    provider_type="local",
                    is_local=True,
                    display_name=f"Local · {model_id}",
                )
            )

    if ENABLE_CLOUD_MODELS:
        for provider_id, model_id in CLOUD_PROVIDERS.items():
            models.append(
                ModelEntry(
                    provider_id=provider_id,
                    model_id=model_id,
                    provider_type="cloud",
                    is_local=False,
                    base_url=DEFAULT_CLOUD_BASE_URL,
                    api_key="",
                    display_name=f"Cloud · {model_id}",
                )
            )

    return models


def get_model_by_provider_id(provider_id: str) -> ModelEntry:
    if provider_id in LOCAL_PROVIDERS:
        return ModelEntry(
            provider_id=provider_id,
            model_id=LOCAL_PROVIDERS[provider_id],
            provider_type="local",
            is_local=True,
            display_name=f"Local · {LOCAL_PROVIDERS[provider_id]}",
        )

    if provider_id in CLOUD_PROVIDERS:
        return ModelEntry(
            provider_id=provider_id,
            model_id=CLOUD_PROVIDERS[provider_id],
            provider_type="cloud",
            is_local=False,
            base_url=DEFAULT_CLOUD_BASE_URL,
            api_key="",
            display_name=f"Cloud · {CLOUD_PROVIDERS[provider_id]}",
        )

    raise KeyError(f"Unknown provider_id: {provider_id!r}")