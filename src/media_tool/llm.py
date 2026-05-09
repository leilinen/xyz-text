"""Unified LLM client using OpenAI-compatible streaming API.

All backends (Zhipu, Ollama, OpenAI, custom) share the same /v1/chat/completions
protocol.  Configuration is resolved in config.py to a single (base_url, api_key, model)
tuple; this module only concerns itself with calling the API and retrying on failure.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Protocol, runtime_checkable

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMClient(Protocol):
    """Any LLM backend must implement this."""

    def complete(self, messages: list[dict[str, str]], temperature: float) -> str:
        """Send messages and return the content string."""
        ...


# ---------------------------------------------------------------------------
# Unified OpenAI-compatible client (streaming)
# ---------------------------------------------------------------------------

class OpenAIStreamingClient:
    """Single client for any OpenAI-compatible API endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str, max_tokens: int = 4096, timeout: int = 120) -> None:
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, messages: list[dict[str, str]], temperature: float) -> str:
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=self._max_tokens,
            stream=True,
        )
        parts: list[str] = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                parts.append(delta.content)
        return "".join(parts)


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

class RetryingClient:
    """Wraps any LLMClient with retry + exponential backoff."""

    def __init__(self, inner: LLMClient, max_retries: int = 3, base_delay: float = 2.0) -> None:
        self._inner = inner
        self._max_retries = max_retries
        self._base_delay = base_delay

    def complete(self, messages: list[dict[str, str]], temperature: float) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return self._inner.complete(messages, temperature)
            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM request failed (attempt %d/%d): %s  retrying in %.1fs",
                        attempt, self._max_retries, exc, delay,
                    )
                    time.sleep(delay)
        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_llm_client(settings: Settings | None = None) -> LLMClient:
    """Create a unified LLM client from settings."""
    settings = settings or get_settings()

    inner: LLMClient = OpenAIStreamingClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
    )

    return RetryingClient(
        inner,
        max_retries=settings.llm_max_retries,
        base_delay=settings.llm_retry_delay,
    )
