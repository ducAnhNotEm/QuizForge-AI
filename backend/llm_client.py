"""Async adapters for the text generation providers used by QuizForge.

Provider calls use HTTPX directly so Gemini, OpenAI, and local Ollama share the
same timeout, retry, and error handling policy. API keys are read from the
environment and are never included in exceptions or logs.
"""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable, Literal, Optional
from urllib.parse import quote

import httpx

from backend.exam_context import estimate_tokens
from backend.prompts import PromptPayload

LLMProviderName = Literal["gemini", "openai", "ollama"]
SUPPORTED_PROVIDERS = frozenset({"gemini", "openai", "ollama"})


@dataclass(frozen=True)
class LLMSettings:
    """Provider credentials and generation/retry settings."""

    provider: LLMProviderName
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: float = 45.0
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 8.0
    temperature: float = 0.2
    top_p: float = 0.9
    max_output_tokens: int = 2048
    max_input_tokens: int = 12000

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider: {self.provider!r}")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.backoff_base_seconds < 0 or self.backoff_max_seconds < 0:
            raise ValueError("backoff delays cannot be negative")
        if self.backoff_max_seconds < self.backoff_base_seconds:
            raise ValueError("backoff_max_seconds must be >= backoff_base_seconds")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be in the range (0, 1]")
        if self.max_output_tokens <= 0 or self.max_input_tokens <= 0:
            raise ValueError("token limits must be positive")

    @classmethod
    def from_env(cls) -> "LLMSettings":
        """Read provider configuration without requiring a dotenv dependency."""

        provider = os.getenv("QUIZFORGE_LLM_PROVIDER", "ollama").strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
            raise LLMConfigurationError(
                f"QUIZFORGE_LLM_PROVIDER must be one of: {supported}"
            )

        model = os.getenv("QUIZFORGE_LLM_MODEL", "").strip()
        if not model:
            raise LLMConfigurationError("Set QUIZFORGE_LLM_MODEL to the model name")

        key_name = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
        api_key = os.getenv(key_name) if key_name else None
        base_url_name = {
            "gemini": "GEMINI_API_BASE_URL",
            "openai": "OPENAI_API_BASE_URL",
            "ollama": "OLLAMA_BASE_URL",
        }[provider]

        try:
            return cls(
                provider=provider,  # type: ignore[arg-type]
                model=model,
                api_key=api_key,
                base_url=os.getenv(base_url_name) or None,
                timeout_seconds=float(os.getenv("QUIZFORGE_LLM_TIMEOUT_SECONDS", "45")),
                max_retries=int(os.getenv("QUIZFORGE_LLM_MAX_RETRIES", "3")),
                backoff_base_seconds=float(
                    os.getenv("QUIZFORGE_LLM_BACKOFF_BASE_SECONDS", "0.5")
                ),
                backoff_max_seconds=float(
                    os.getenv("QUIZFORGE_LLM_BACKOFF_MAX_SECONDS", "8")
                ),
                temperature=float(os.getenv("QUIZFORGE_LLM_TEMPERATURE", "0.2")),
                top_p=float(os.getenv("QUIZFORGE_LLM_TOP_P", "0.9")),
                max_output_tokens=int(
                    os.getenv("QUIZFORGE_LLM_MAX_OUTPUT_TOKENS", "2048")
                ),
                max_input_tokens=int(
                    os.getenv("QUIZFORGE_LLM_MAX_INPUT_TOKENS", "12000")
                ),
            )
        except ValueError as exc:
            raise LLMConfigurationError(f"Invalid LLM configuration: {exc}") from exc


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None


class LLMError(RuntimeError):
    """Base class for provider and configuration errors."""


class LLMConfigurationError(LLMError):
    """Provider configuration is missing or invalid."""


class LLMProviderError(LLMError):
    """A non-retryable provider or response-format error."""


class LLMInputTooLargeError(LLMError):
    """The prompt exceeds the configured estimated input-token limit."""


class LLMTransientError(LLMError):
    """A network/provider error that may succeed if retried."""

    def __init__(self, message: str, *, retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMRateLimitError(LLMTransientError):
    """The provider asked the client to slow down."""


SleepFunction = Callable[[float], Awaitable[None]]
RandomFunction = Callable[[], float]


class LLMClient:
    """Generate text through Gemini, OpenAI, or Ollama with bounded retries.

    ``http_client`` is injectable for tests. If supplied, its lifecycle remains
    owned by the caller; otherwise this client creates and closes its own.
    """

    def __init__(
        self,
        settings: LLMSettings,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        sleep: SleepFunction = asyncio.sleep,
        random_value: RandomFunction = random.random,
    ) -> None:
        self.settings = settings
        self._http_client = http_client or httpx.AsyncClient()
        self._owns_http_client = http_client is None
        self._sleep = sleep
        self._random_value = random_value

    @classmethod
    def from_env(cls, **kwargs: Any) -> "LLMClient":
        return cls(LLMSettings.from_env(), **kwargs)

    async def generate(self, payload: PromptPayload) -> LLMResponse:
        """Call the configured provider and return its raw text response.

        The text is intentionally not parsed here. SV3's quality gate owns
        JSON parsing and validation against the target question schema.
        """

        estimated_tokens = sum(estimate_tokens(message.get("content", "")) for message in payload.messages)
        if estimated_tokens > self.settings.max_input_tokens:
            raise LLMInputTooLargeError(
                "Estimated prompt size "
                f"({estimated_tokens} tokens) exceeds configured limit "
                f"({self.settings.max_input_tokens})"
            )

        for attempt in range(self.settings.max_retries + 1):
            try:
                return await self._request_provider(payload)
            except LLMTransientError as exc:
                if attempt >= self.settings.max_retries:
                    raise
                delay = self._retry_delay(attempt, exc)
                await self._sleep(delay)

        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.aclose()

    def _retry_delay(self, attempt: int, error: LLMTransientError) -> float:
        if error.retry_after_seconds is not None:
            # A provider-supplied Retry-After is a minimum wait; do not retry
            # earlier just because our exponential-backoff cap is lower.
            return max(0.0, error.retry_after_seconds)
        exponential = self.settings.backoff_base_seconds * (2**attempt)
        # Small jitter prevents concurrent requests from retrying in lockstep.
        jitter = exponential * 0.1 * min(max(self._random_value(), 0.0), 1.0)
        return min(exponential + jitter, self.settings.backoff_max_seconds)

    async def _request_provider(self, payload: PromptPayload) -> LLMResponse:
        if self.settings.provider == "gemini":
            return await self._request_gemini(payload)
        if self.settings.provider == "openai":
            return await self._request_openai(payload)
        return await self._request_ollama(payload)

    async def _post_json(
        self,
        url: str,
        body: dict[str, Any],
        *,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                url,
                json=body,
                headers=headers,
                timeout=self.settings.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LLMTransientError("LLM provider request timed out") from exc
        except httpx.NetworkError as exc:
            raise LLMTransientError("Could not connect to LLM provider") from exc
        except httpx.RequestError as exc:
            raise LLMTransientError("LLM provider request failed") from exc

        if response.status_code >= 400:
            status = response.status_code
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            if status == 429:
                raise LLMRateLimitError(
                    "LLM provider rate limit reached", retry_after_seconds=retry_after
                )
            if status in {408, 425} or status >= 500:
                raise LLMTransientError(
                    f"LLM provider returned temporary HTTP {status}",
                    retry_after_seconds=retry_after,
                )
            if status in {401, 403}:
                raise LLMConfigurationError(
                    f"LLM provider rejected credentials (HTTP {status})"
                )
            raise LLMProviderError(f"LLM provider rejected the request (HTTP {status})")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("LLM provider returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LLMProviderError("LLM provider returned an unexpected response")
        return data

    async def _request_gemini(self, payload: PromptPayload) -> LLMResponse:
        if not self.settings.api_key:
            raise LLMConfigurationError("Set GEMINI_API_KEY to use the Gemini provider")
        base_url = (self.settings.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        model = quote(self.settings.model, safe="")
        url = f"{base_url}/models/{model}:generateContent"

        system_text = "\n\n".join(
            message["content"] for message in payload.messages if message.get("role") == "system"
        )
        contents = [
            {
                "role": "model" if message.get("role") == "assistant" else "user",
                "parts": [{"text": message.get("content", "")}],
            }
            for message in payload.messages
            if message.get("role") != "system"
        ]
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.settings.temperature,
                "topP": self.settings.top_p,
                "maxOutputTokens": self.settings.max_output_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": payload.response_schema,
            },
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}

        data = await self._post_json(
            url, body, headers={"x-goog-api-key": self.settings.api_key}
        )
        candidates = data.get("candidates") or []
        if not candidates:
            feedback = data.get("promptFeedback") or {}
            reason = feedback.get("blockReason") or "no candidate returned"
            raise LLMProviderError(f"Gemini did not return a text candidate ({reason})")
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        content = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        if not content:
            raise LLMProviderError("Gemini returned an empty text response")
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            content=content,
            provider="gemini",
            model=data.get("modelVersion") or self.settings.model,
            prompt_tokens=_optional_int(usage.get("promptTokenCount")),
            completion_tokens=_optional_int(usage.get("candidatesTokenCount")),
            finish_reason=candidate.get("finishReason"),
        )

    async def _request_openai(self, payload: PromptPayload) -> LLMResponse:
        if not self.settings.api_key:
            raise LLMConfigurationError("Set OPENAI_API_KEY to use the OpenAI provider")
        base_url = (self.settings.base_url or "https://api.openai.com/v1").rstrip("/")
        body = {
            "model": self.settings.model,
            "messages": payload.messages,
            "temperature": self.settings.temperature,
            "top_p": self.settings.top_p,
            "max_completion_tokens": self.settings.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        data = await self._post_json(
            f"{base_url}/chat/completions",
            body,
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
        )
        choices = data.get("choices") or []
        if not choices:
            raise LLMProviderError("OpenAI returned no completion choices")
        choice = choices[0]
        content = ((choice.get("message") or {}).get("content") or "").strip()
        if not content:
            raise LLMProviderError("OpenAI returned an empty text response")
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            provider="openai",
            model=data.get("model") or self.settings.model,
            prompt_tokens=_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_int(usage.get("completion_tokens")),
            finish_reason=choice.get("finish_reason"),
        )

    async def _request_ollama(self, payload: PromptPayload) -> LLMResponse:
        base_url = (self.settings.base_url or "http://127.0.0.1:11434").rstrip("/")
        body = {
            "model": self.settings.model,
            "messages": payload.messages,
            "stream": False,
            "format": payload.response_schema,
            "options": {
                "temperature": self.settings.temperature,
                "top_p": self.settings.top_p,
                "num_predict": self.settings.max_output_tokens,
            },
        }
        data = await self._post_json(f"{base_url}/api/chat", body)
        content = ((data.get("message") or {}).get("content") or "").strip()
        if not content:
            raise LLMProviderError("Ollama returned an empty text response")
        return LLMResponse(
            content=content,
            provider="ollama",
            model=data.get("model") or self.settings.model,
            prompt_tokens=_optional_int(data.get("prompt_eval_count")),
            completion_tokens=_optional_int(data.get("eval_count")),
            finish_reason=data.get("done_reason"),
        )


def _optional_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None
