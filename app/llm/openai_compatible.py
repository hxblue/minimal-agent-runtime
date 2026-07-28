"""OpenAI-compatible Chat Completions transport without an Agent SDK."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.errors import LLMHTTPError, LLMProtocolError, LLMTimeoutError
from app.models import LLMResponse, Message, TokenUsage, ToolCall
from app.protocols import LLMToolSpec


class OpenAICompatibleClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if not model.strip():
            raise ValueError("model must not be empty")
        self._http_client = http_client
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model.strip()
        self._temperature = temperature

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._serialize_message(message) for message in messages],
            "temperature": self._temperature,
        }
        if allow_tools and tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = await self._http_client.post(
                self._endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMHTTPError(exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise LLMHTTPError(0, "LLM transport failed") from exc

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMProtocolError("LLM response was not valid JSON") from exc
        return self.parse_response(data)

    @staticmethod
    def _serialize_message(message: Message) -> dict[str, Any]:
        serialized: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }
        if message.role == "assistant" and message.tool_calls:
            serialized["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments_json,
                    },
                }
                for call in message.tool_calls
            ]
        if message.role == "tool":
            serialized["tool_call_id"] = message.tool_call_id
        return serialized

    @staticmethod
    def parse_response(data: Any) -> LLMResponse:
        if not isinstance(data, Mapping):
            raise LLMProtocolError("LLM response must be a JSON object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProtocolError("LLM response did not contain choices")
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise LLMProtocolError("LLM choice must be an object")
        message = choice.get("message")
        if not isinstance(message, Mapping):
            raise LLMProtocolError("LLM choice did not contain a message")

        content_value = message.get("content")
        content = content_value if isinstance(content_value, str) else None
        calls = OpenAICompatibleClient._parse_tool_calls(message.get("tool_calls", []))
        finish_reason_value = choice.get("finish_reason")
        finish_reason = (
            finish_reason_value if isinstance(finish_reason_value, str) else None
        )
        usage = OpenAICompatibleClient._parse_usage(data.get("usage"))
        try:
            return LLMResponse(
                final_text=content,
                tool_calls=calls,
                finish_reason=finish_reason,
                usage=usage,
            )
        except ValueError as exc:
            raise LLMProtocolError("LLM message had neither text nor tool calls") from exc

    @staticmethod
    def _parse_tool_calls(value: Any) -> list[ToolCall]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise LLMProtocolError("tool_calls must be a list")
        calls: list[ToolCall] = []
        for raw_call in value:
            if not isinstance(raw_call, Mapping):
                raise LLMProtocolError("tool call must be an object")
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                raise LLMProtocolError("tool call function must be an object")
            call_id = raw_call.get("id")
            name = function.get("name")
            arguments = function.get("arguments", "{}")
            if not isinstance(call_id, str) or not call_id:
                raise LLMProtocolError("tool call id is missing")
            if not isinstance(name, str) or not name:
                raise LLMProtocolError("tool call name is missing")
            if isinstance(arguments, Mapping):
                arguments = json.dumps(arguments, ensure_ascii=False)
            if not isinstance(arguments, str):
                raise LLMProtocolError("tool call arguments must be JSON text")
            calls.append(
                ToolCall(id=call_id, name=name, arguments_json=arguments)
            )
        return calls

    @staticmethod
    def _parse_usage(value: Any) -> TokenUsage | None:
        if not isinstance(value, Mapping):
            return None

        def integer(name: str) -> int:
            raw = value.get(name, 0)
            return raw if isinstance(raw, int) and raw >= 0 else 0

        return TokenUsage(
            prompt_tokens=integer("prompt_tokens"),
            completion_tokens=integer("completion_tokens"),
            total_tokens=integer("total_tokens"),
        )

