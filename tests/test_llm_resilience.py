"""Unit tests for async provider requests and transient-error retry policy."""

import asyncio
import json

import httpx
import pytest

from backend.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMInputTooLargeError,
    LLMProviderError,
    LLMRateLimitError,
    LLMSettings,
    LLMTransientError,
)
from backend.prompts import PromptPayload


def make_payload():
    return PromptPayload(
        messages=[
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Create one question from this lesson."},
        ],
        source_refs=(),
        prompt_version="test-v1",
        response_schema={"type": "object", "properties": {"questions": {"type": "array"}}},
    )


def make_settings(provider, **overrides):
    values = {
        "provider": provider,
        "model": "test-model",
        "api_key": "test-key" if provider in {"gemini", "openai"} else None,
        "max_retries": 2,
        "backoff_base_seconds": 0.01,
        "backoff_max_seconds": 0.1,
    }
    values.update(overrides)
    return LLMSettings(**values)


def make_http_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_openai_request_uses_async_chat_payload_and_reads_usage():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "choices": [
                        {"message": {"content": '{"questions": []}'}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 19, "completion_tokens": 7},
                },
            )

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("openai", base_url="https://openai.test/v1"),
            http_client=transport,
        )
        try:
            result = await client.generate(make_payload())
        finally:
            await transport.aclose()

        assert requests[0].url.path == "/v1/chat/completions"
        assert requests[0].headers["authorization"] == "Bearer test-key"
        request_json = json.loads(requests[0].content)
        assert request_json["messages"] == make_payload().messages
        assert request_json["max_completion_tokens"] == 2048
        assert request_json["response_format"] == {"type": "json_object"}
        assert result.content == '{"questions": []}'
        assert result.prompt_tokens == 19
        assert result.completion_tokens == 7

    asyncio.run(scenario())


def test_gemini_request_uses_system_instruction_and_json_schema():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "modelVersion": "test-model-version",
                    "candidates": [
                        {
                            "content": {"parts": [{"text": '{"questions": []}'}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 21, "candidatesTokenCount": 8},
                },
            )

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("gemini", base_url="https://gemini.test/v1beta"),
            http_client=transport,
        )
        try:
            result = await client.generate(make_payload())
        finally:
            await transport.aclose()

        request = requests[0]
        assert request.url.path.endswith("/models/test-model:generateContent")
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["systemInstruction"]["parts"][0]["text"] == "Return JSON only."
        assert body["generationConfig"]["responseJsonSchema"] == make_payload().response_schema
        assert body["generationConfig"]["maxOutputTokens"] == 2048
        assert result.provider == "gemini"
        assert result.prompt_tokens == 21
        assert result.completion_tokens == 8

    asyncio.run(scenario())


def test_ollama_request_uses_local_chat_api_and_generation_options():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": '{"questions": []}'},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 14,
                    "eval_count": 9,
                },
            )

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("ollama", base_url="http://ollama.test:11434"),
            http_client=transport,
        )
        try:
            result = await client.generate(make_payload())
        finally:
            await transport.aclose()

        request = requests[0]
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["format"] == make_payload().response_schema
        assert body["options"]["num_predict"] == 2048
        assert result.prompt_tokens == 14
        assert result.completion_tokens == 9

    asyncio.run(scenario())


def test_retries_rate_limit_then_returns_success():
    async def scenario():
        calls = 0
        delays = []

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "slow down"})
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"questions": []}'}, "finish_reason": "stop"}]
                },
            )

        async def fake_sleep(delay):
            delays.append(delay)

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("openai", base_url="https://openai.test/v1"),
            http_client=transport,
            sleep=fake_sleep,
        )
        try:
            result = await client.generate(make_payload())
        finally:
            await transport.aclose()

        assert calls == 2
        assert delays == [0.0]
        assert result.content == '{"questions": []}'

    asyncio.run(scenario())


def test_retries_network_timeout_with_exponential_backoff():
    async def scenario():
        calls = 0
        delays = []

        def handler(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("mock timeout")
            return httpx.Response(
                200,
                json={"message": {"content": '{"questions": []}'}, "done_reason": "stop"},
            )

        async def fake_sleep(delay):
            delays.append(delay)

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("ollama", base_url="http://ollama.test", max_retries=1),
            http_client=transport,
            sleep=fake_sleep,
            random_value=lambda: 0.0,
        )
        try:
            result = await client.generate(make_payload())
        finally:
            await transport.aclose()

        assert calls == 2
        assert delays == [0.01]
        assert result.provider == "ollama"

    asyncio.run(scenario())


def test_non_retryable_auth_error_is_not_retried():
    async def scenario():
        calls = 0
        delays = []

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(401, json={"error": "invalid key"})

        async def fake_sleep(delay):
            delays.append(delay)

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("openai", base_url="https://openai.test/v1"),
            http_client=transport,
            sleep=fake_sleep,
        )
        try:
            with pytest.raises(LLMConfigurationError):
                await client.generate(make_payload())
        finally:
            await transport.aclose()

        assert calls == 1
        assert delays == []

    asyncio.run(scenario())


def test_estimated_prompt_limit_fails_before_network_request():
    async def scenario():
        calls = 0

        def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(500)

        transport = make_http_client(handler)
        client = LLMClient(
            make_settings("ollama", max_input_tokens=1), http_client=transport
        )
        try:
            with pytest.raises(LLMInputTooLargeError, match="exceeds configured limit"):
                await client.generate(make_payload())
        finally:
            await transport.aclose()
        assert calls == 0

    asyncio.run(scenario())


def test_invalid_provider_configuration_is_rejected():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        LLMSettings(provider="unknown", model="test")


def test_transient_error_type_is_retryable():
    error = LLMRateLimitError("rate limited", retry_after_seconds=2.0)
    assert isinstance(error, LLMTransientError)
    assert error.retry_after_seconds == 2.0
