"""
core/providers.py — Provider abstraction layer for PetChat-2.0.

The rest of the app calls provider.chat() only; HTTP details are hidden here.

Supported backends
------------------
CloudProvider  — OpenAI-compatible REST endpoint (Groq, OpenAI, Google Gemini)
LocalProvider  — Ollama HTTP API (http://localhost:11434)

Factory
-------
build_provider(session_config) -> BaseProvider
    Creates the correct concrete provider from the session_config dict that
    ModelSetupPage emits and MainWindow forwards to ChatPage.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from petchat.config import (
    CLOUD_PROVIDERS,
    GROQ_API_KEY,
    GOOGLE_API_KEY,
    OPENAI_API_KEY,
    LOCAL_PROVIDERS,
    OLLAMA_BASE_URL,
)


# ---------------------------------------------------------------------------
# Endpoint registry
# ---------------------------------------------------------------------------

# Maps provider_id -> (base_url, default_api_key)
_CLOUD_ENDPOINTS: dict[str, tuple[str, str]] = {
    "llama_scout": ("https://api.groq.com/openai/v1", GROQ_API_KEY),
    "secondary":   ("https://generativelanguage.googleapis.com/v1beta/openai", GOOGLE_API_KEY),
}

# Fallback for any unknown provider_id — assumes OpenAI-compatible.
_DEFAULT_CLOUD_ENDPOINT = ("https://api.openai.com/v1", OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ProviderError(RuntimeError):
    """Non-retryable error returned by a provider (bad key, model not found…)."""


class ProviderTimeout(ProviderError):
    """Request exceeded the timeout threshold."""


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseProvider(ABC):
    """
    Minimal interface every provider must implement.

    Parameters
    ----------
    model_id   : Full model string forwarded to the inference API.
    provider_id: Stable key from config.py — used for endpoint lookup.
    api_key    : Bearer token (empty string for local providers).
    """

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        api_key: str = "",
    ) -> None:
        self.model_id    = model_id
        self.provider_id = provider_id
        self.api_key     = api_key

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """
        Send a chat completion request and return the assistant reply text.

        Parameters
        ----------
        messages    : OpenAI-style message list [{"role": …, "content": …}, …]
        temperature : Sampling temperature.
        max_tokens  : Upper bound on reply length.

        Raises
        ------
        ProviderError   : Any non-retryable API / model error.
        ProviderTimeout : Request timed out.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_id={self.model_id!r})"


# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------

def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Minimal JSON POST using only the stdlib (no httpx / requests dependency).
    Returns the parsed JSON response body.
    """
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise ProviderError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except TimeoutError as exc:
        raise ProviderTimeout(f"Request to {url} timed out after {timeout}s") from exc
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"Request to {url} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# CloudProvider
# ---------------------------------------------------------------------------

class CloudProvider(BaseProvider):
    """
    OpenAI-compatible chat completions endpoint.

    Works with:
    - Groq  (llama-4-scout, llama3, mixtral, …)
    - OpenAI
    - Google Gemini (via its OpenAI-compatible layer)
    - Any other provider that follows the /v1/chat/completions spec.
    """

    _TIMEOUT_S = 90

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        api_key: str = "",
    ) -> None:
        super().__init__(model_id, provider_id, api_key)

        base_url, default_key = _CLOUD_ENDPOINTS.get(
            provider_id, _DEFAULT_CLOUD_ENDPOINT
        )
        self._endpoint = f"{base_url}/chat/completions"
        self._api_key  = api_key or default_key

        if not self._api_key:
            raise ProviderError(
                f"No API key found for provider '{provider_id}'. "
                "Set it in the model setup screen or via an environment variable."
            )

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        payload = {
            "model":       self.model_id,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        data = _post_json(self._endpoint, payload, headers, self._TIMEOUT_S)
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"Unexpected response shape: {data}") from exc


# ---------------------------------------------------------------------------
# LocalProvider  (Ollama)
# ---------------------------------------------------------------------------

class LocalProvider(BaseProvider):
    """
    Ollama HTTP API provider.

    Uses the /api/chat endpoint which accepts OpenAI-style messages and
    returns a streaming or single-shot JSON response.

    Non-streaming mode is used (stream: false) for simplicity.
    """

    _TIMEOUT_S = 120

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        api_key: str = "",          # unused for local; accepted for API symmetry
        base_url: str = "",
    ) -> None:
        super().__init__(model_id, provider_id, api_key)
        self._base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")
        self._endpoint = f"{self._base_url}/api/chat"

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        payload: dict[str, Any] = {
            "model":    self.model_id,
            "messages": messages,
            "stream":   False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        headers = {"Content-Type": "application/json"}
        data = _post_json(self._endpoint, payload, headers, self._TIMEOUT_S)
        try:
            return data["message"]["content"].strip()
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"Unexpected Ollama response: {data}") from exc


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_provider(session_config: dict[str, Any]) -> BaseProvider:
    """
    Instantiate the correct provider from a session_config dict.

    session_config keys consumed
    ----------------------------
    provider_type : "cloud" | "local"
    provider_id   : stable key (e.g. "llama_scout", "llama3_2_3b")
    model_id      : full model string forwarded to the API
    api_key       : bearer token (empty for local)
    is_local      : bool (alternative branch selector)

    Raises
    ------
    ProviderError if provider_type is unrecognised.
    """
    ptype       = session_config.get("provider_type", "")
    is_local    = session_config.get("is_local", False)
    provider_id = session_config.get("provider_id", "")
    model_id    = session_config.get("model_id", "")
    api_key     = session_config.get("api_key", "")

    if ptype == "local" or is_local:
        return LocalProvider(
            model_id=model_id,
            provider_id=provider_id,
        )
    elif ptype == "cloud" or not is_local:
        return CloudProvider(
            model_id=model_id,
            provider_id=provider_id,
            api_key=api_key,
        )
    else:
        raise ProviderError(f"Unknown provider_type: {ptype!r}")


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def list_cloud_models() -> list[dict[str, str]]:
    """
    Return all configured cloud models as a list of dicts.
    No network call is made — returns config values only.
    """
    return [
        {"provider_id": pid, "model_id": mid, "provider_type": "cloud"}
        for pid, mid in CLOUD_PROVIDERS.items()
    ]


def list_local_models(probe: bool = False) -> list[dict[str, str]]:
    """
    Return available local models.

    Parameters
    ----------
    probe : If True, query Ollama's /api/tags for actually-installed models
            and merge with the config list. Falls back to config-only on
            any connection error.
    """
    config_models = [
        {
            "provider_id":   pid,
            "model_id":      mid,
            "provider_type": "local",
            "installed":     False,
        }
        for pid, mid in LOCAL_PROVIDERS.items()
    ]

    if not probe:
        return config_models

    try:
        url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read())
        installed_names = {m["name"] for m in data.get("models", [])}

        reverse = {v: k for k, v in LOCAL_PROVIDERS.items()}
        result = []
        for m in config_models:
            m["installed"] = m["model_id"] in installed_names
            result.append(m)

        known_ids = {m["model_id"] for m in config_models}
        for name in installed_names:
            if name not in known_ids:
                result.append({
                    "provider_id":   reverse.get(name, name),
                    "model_id":      name,
                    "provider_type": "local",
                    "installed":     True,
                })
        return result

    except Exception:  # noqa: BLE001
        return config_models