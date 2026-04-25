"""
core/providers.py -- Provider abstraction layer for PetChat-2.0 v2.

The rest of the app should only call provider.chat(...).
This module hides HTTP details for:
- Local Ollama models
- Cloud OpenAI-compatible chat completion APIs
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from src.config import OLLAMA_BASE_URL


class ProviderError(RuntimeError):
    """Raised when a provider request fails in a non-retryable way."""


class ProviderTimeout(ProviderError):
    """Raised when a provider request times out."""


class BaseProvider(ABC):
    """
    Abstract provider interface used by the pipeline.
    """

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> None:
        self.model_id = (model_id or "").strip()
        self.provider_id = (provider_id or "").strip()
        self.base_url = (base_url or "").strip()
        self.api_key = (api_key or "").strip()

        if not self.model_id:
            raise ProviderError("model_id is required.")

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """
        Send a chat request and return the assistant text.
        """

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model_id={self.model_id!r}, provider_id={self.provider_id!r})"
        )


def _normalize_base_url(base_url: str, suffix: str) -> str:
    clean = (base_url or "").rstrip("/")
    if not clean:
        return suffix
    if clean.endswith(suffix):
        return clean
    return f"{clean}{suffix}"


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: int = 90,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code} from provider: {detail}") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, socket.timeout):
            raise ProviderTimeout("Provider request timed out.") from exc
        raise ProviderError(f"Could not reach provider: {reason}") from exc
    except TimeoutError as exc:
        raise ProviderTimeout("Provider request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned invalid JSON.") from exc
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"Provider request failed: {exc}") from exc


class CloudProvider(BaseProvider):
    """
    OpenAI-compatible cloud provider.

    Expects:
    - base_url like https://api.openai.com/v1
    - api_key
    - model_id
    """

    _TIMEOUT_S = 90

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> None:
        super().__init__(
            model_id=model_id,
            provider_id=provider_id,
            base_url=base_url,
            api_key=api_key,
        )

        if not self.base_url:
            raise ProviderError("Cloud provider requires base_url.")
        if not self.api_key:
            raise ProviderError("Cloud provider requires api_key.")

        self.endpoint = _normalize_base_url(self.base_url, "/chat/completions")

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        data = _post_json(
            url=self.endpoint,
            payload=payload,
            headers=headers,
            timeout=self._TIMEOUT_S,
        )

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected cloud response shape: {data}"
            ) from exc

        if not isinstance(content, str):
            raise ProviderError("Cloud provider returned non-text content.")

        return content.strip()


class LocalProvider(BaseProvider):
    """
    Ollama local provider using the HTTP API.

    Supports local models such as:
    - phi4-mini:latest
    - llama3.2:3b
    """

    _TIMEOUT_S = 120
    _SUPPORTED_MODELS = {
        "phi4-mini:latest",
        "llama3.2:3b",
    }

    def __init__(
        self,
        model_id: str,
        provider_id: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> None:
        resolved_base_url = (base_url or OLLAMA_BASE_URL or "").rstrip("/")
        super().__init__(
            model_id=model_id,
            provider_id=provider_id,
            base_url=resolved_base_url,
            api_key=api_key,
        )

        if not self.base_url:
            raise ProviderError("Local provider requires OLLAMA_BASE_URL.")

        self.endpoint = f"{self.base_url}/api/chat"

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        if self.model_id not in self._SUPPORTED_MODELS:
            raise ProviderError(
                f"Unsupported local model: {self.model_id}. "
                "Supported models are phi4-mini:latest and llama3.2:3b."
            )

        payload = {
            "model": self.model_id,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        headers = {"Content-Type": "application/json"}

        data = _post_json(
            url=self.endpoint,
            payload=payload,
            headers=headers,
            timeout=self._TIMEOUT_S,
        )

        try:
            content = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                f"Unexpected Ollama response shape: {data}"
            ) from exc

        if not isinstance(content, str):
            raise ProviderError("Local provider returned non-text content.")

        return content.strip()


def build_provider(session_config: dict[str, Any]) -> BaseProvider:
    """
    Build a provider instance from session_config.

    Expected keys:
    - provider_type: "local" or "cloud"
    - provider_id: stable internal id
    - model_id: actual model string
    - base_url: required for cloud, optional for local
    - api_key: required for cloud
    - is_local: bool
    """
    config = session_config or {}

    provider_type = str(config.get("provider_type", "")).strip().lower()
    provider_id = str(config.get("provider_id", "")).strip()
    model_id = str(config.get("model_id", "")).strip()
    base_url = str(config.get("base_url", "")).strip()
    api_key = str(config.get("api_key", "")).strip()
    is_local = bool(config.get("is_local", False))

    if provider_type == "local" or is_local:
        return LocalProvider(
            model_id=model_id,
            provider_id=provider_id,
            base_url=base_url,
            api_key="",
        )

    if provider_type == "cloud":
        return CloudProvider(
            model_id=model_id,
            provider_id=provider_id,
            base_url=base_url,
            api_key=api_key,
        )

    if provider_id in {"phi4_mini", "llama3_2_3b"}:
        return LocalProvider(
            model_id=model_id,
            provider_id=provider_id,
            base_url=base_url,
            api_key="",
        )

    raise ProviderError(f"Unknown provider configuration: {session_config!r}")