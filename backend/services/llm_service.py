"""Provider-agnostic LLM client.

Supported providers
-------------------
* ``grok``       xAI, OpenAI-compatible (https://api.x.ai/v1)
* ``openai``     OpenAI Chat Completions
* ``openrouter`` OpenRouter free models (OpenAI-compatible)
* ``ollama``     local models, OpenAI-compatible endpoint
* ``gemini``     Google Generative Language API
* ``demo``       no key required — deterministic local planner

The rest of the app only ever sees ``LLMResponse`` objects, so switching
providers is a one-line ``.env`` change.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from backend.config import Settings, get_settings
from backend.services.circuit_breaker import call_with_breaker, CircuitBreakerOpenError


class LLMError(RuntimeError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


OPENAI_COMPATIBLE = {
    "grok": ("https://api.x.ai/v1/chat/completions", "grok-2-latest", "xai_api_key"),
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini", "openai_api_key"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "meta-llama/llama-3.3-70b-instruct:free", "openrouter_api_key"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b", "groq_api_key"),
    "nvidia": ("https://integrate.api.nvidia.com/v1/chat/completions", "meta/llama-3.3-70b-instruct", "nvidia_api_key"),
}

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = (self.settings.llm_provider or "demo").lower()

    # ------------------------------------------------------------------ #
    # Capability checks
    # ------------------------------------------------------------------ #
    @property
    def is_live(self) -> bool:
        if self.provider == "demo":
            return False
        if self.provider in OPENAI_COMPATIBLE:
            return bool(self.settings.groq_key_list) if self.provider == "groq" else bool(getattr(self.settings, OPENAI_COMPATIBLE[self.provider][2], "").strip())
        if self.provider == "gemini":
            return bool(self.settings.gemini_api_key.strip())
        if self.provider == "ollama":
            return True
        return False

    @property
    def model(self) -> str:
        if self.settings.llm_model:
            return self.settings.llm_model
        if self.provider in OPENAI_COMPATIBLE:
            return OPENAI_COMPATIBLE[self.provider][1]
        if self.provider == "ollama":
            return "llama3.2"
        if self.provider == "gemini":
            return GEMINI_MODEL
        return "local-planner"

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "live": self.is_live,
            "fallback": "deterministic local planner",
        }

    # ------------------------------------------------------------------ #
    # Chat completion
    # ------------------------------------------------------------------ #
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        if not self.is_live:
            raise LLMError("No live LLM configured; using the local planner")
        if self.provider == "gemini":
            return await self._gemini_complete(messages, tools, temperature)
        if self.provider == "groq":
            return await self._groq_complete_with_rotation(messages, tools, temperature)
        return await self._openai_complete(messages, tools, temperature)

    async def _groq_complete_with_rotation(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
    ) -> LLMResponse:
        """Try each configured Groq key in order; rotate on 429 rate-limit."""
        keys = self.settings.groq_key_list
        if not keys:
            raise LLMError("No Groq API key configured; using the local planner")
        last_exc: LLMError | None = None
        for idx, key in enumerate(keys):
            try:
                return await self._openai_complete(messages, tools, temperature, api_key=key)
            except LLMError as exc:
                last_exc = exc
                is_rate_limit = "429" in str(exc) or "rate_limit" in str(exc).lower()
                if idx < len(keys) - 1 and is_rate_limit:
                    logger = logging.getLogger("mindtrip.llm")
                    logger.warning(
                        "Groq key %d rate-limited (429); rotating to key %d/%d",
                        idx + 1, idx + 2, len(keys),
                    )
                    continue
                raise
        raise last_exc  # unreachable but satisfies type checker

    async def complete_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_retries: int = 0,
        base_delay: float = 1.0,
    ) -> LLMResponse:
        """Complete with fail-fast behavior on rate limits.

        ``max_retries=0`` by default because Groq 429s are hard token limits —
        retrying the same key is wasted time. Key rotation inside
        ``_groq_complete_with_rotation`` already tries every configured key once
        before giving up. Only transient network errors (5xx) benefit from a
        single retry.
        """
        import logging

        logger = logging.getLogger("mindtrip.llm")
        last_exc: LLMError | None = None
        for attempt in range(max_retries + 1):
            try:
                return await self.complete(messages, tools, temperature)
            except LLMError as exc:
                last_exc = exc
                is_rate_limit = "429" in str(exc) or "rate_limit" in str(exc).lower()
                if is_rate_limit:
                    # Rate limits are hard quotas; retrying won't help. Surface
                    # immediately so the caller can fall back to the local planner.
                    logger.warning("LLM rate limit hit; failing fast to local planner: %s", exc)
                    raise
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s; retrying in %.1fs",
                        attempt + 1, max_retries + 1, exc, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        raise last_exc  # unreachable but satisfies type checker

    async def _openai_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        api_key: str | None = None,
    ) -> LLMResponse:
        if self.provider == "ollama":
            url = f"{self.settings.ollama_base_url.rstrip('/')}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
        else:
            url, _, key_attr = OPENAI_COMPATIBLE[self.provider]
            effective_key = api_key or getattr(self.settings, key_attr)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {effective_key}",
            }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        def _do_request() -> LLMResponse:
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.llm_timeout_seconds,
                )
            except Exception as exc:
                raise LLMError(f"{self.provider} request failed: {exc}") from exc
            if response.status_code >= 400:
                raise LLMError(f"{self.provider} returned {response.status_code}: {response.text[:400]}")
            data = response.json()
            try:
                message = data["choices"][0]["message"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Unexpected {self.provider} response: {data}") from exc
            calls = []
            for call in message.get("tool_calls") or []:
                function = call.get("function", {})
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                calls.append(
                    ToolCall(id=call.get("id", ""), name=function.get("name", ""), arguments=arguments)
                )
            return LLMResponse(content=message.get("content") or "", tool_calls=calls, raw=data)

        breaker_name = f"llm:{self.provider}"
        try:
            return call_with_breaker(breaker_name, _do_request)
        except CircuitBreakerOpenError as exc:
            raise LLMError(str(exc)) from exc

    async def _gemini_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
    ) -> LLMResponse:
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        contents = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": message.get("content", "")}],
                }
            )
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": self.settings.llm_temperature if temperature is None else temperature},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool["function"]["name"],
                            "description": tool["function"].get("description", ""),
                            "parameters": tool["function"].get("parameters", {}),
                        }
                        for tool in tools
                    ]
                }
            ]
        url = GEMINI_URL.format(model=self.model)

        def _do_request() -> LLMResponse:
            try:
                response = httpx.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.settings.llm_timeout_seconds,
                )
            except Exception as exc:
                raise LLMError(f"gemini request failed: {exc}") from exc
            if response.status_code >= 400:
                raise LLMError(f"gemini returned {response.status_code}: {response.text[:400]}")
            data = response.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Unexpected gemini response: {data}") from exc
            text_parts, calls = [], []
            for part in parts:
                if "text" in part:
                    text_parts.append(part["text"])
                if "functionCall" in part:
                    call = part["functionCall"]
                    calls.append(
                        ToolCall(
                            id=call.get("name", ""),
                            name=call.get("name", ""),
                            arguments=call.get("args") or {},
                        )
                    )
            return LLMResponse(content="".join(text_parts), tool_calls=calls, raw=data)

        breaker_name = "llm:gemini"
        try:
            return call_with_breaker(breaker_name, _do_request)
        except CircuitBreakerOpenError as exc:
            raise LLMError(str(exc)) from exc

    # ------------------------------------------------------------------ #
    # Streaming (best-effort; the chat endpoint chunks text regardless)
    # ------------------------------------------------------------------ #
    async def stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        if not self.is_live or self.provider == "gemini":
            response = await self.complete(messages)
            for chunk in _chunk(response.content, 18):
                yield chunk
            return

        if self.provider == "ollama":
            url = f"{self.settings.ollama_base_url.rstrip('/')}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
        else:
            url, _, key_attr = OPENAI_COMPATIBLE[self.provider]
            headers = {"Authorization": f"Bearer {getattr(self.settings, key_attr)}", "Content-Type": "application/json"}

        payload = {"model": self.model, "messages": messages, "stream": True, "temperature": self.settings.llm_temperature}
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise LLMError(f"{self.provider} stream error {response.status_code}: {body[:300]!r}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {}).get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta


def _chunk(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]
