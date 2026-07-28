from __future__ import annotations

import json

import httpx
import pytest

from app.errors import LLMHTTPError, LLMProtocolError, LLMTimeoutError
from app.llm.openai_compatible import OpenAICompatibleClient
from app.models import Message, ToolCall


def make_response(*, content="hello", tool_calls=None, status=200):
    return httpx.Response(
        status,
        json={
            "choices": [
                {
                    "message": {"role": "assistant", "content": content, "tool_calls": tool_calls},
                    "finish_reason": "tool_calls" if tool_calls else "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        },
    )


async def test_client_sends_messages_tools_and_secret_header() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return make_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAICompatibleClient(
            http_client,
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="demo-model",
        )
        result = await client.complete(
            [Message(session_id="s", role="user", content="Hi")],
            [
                {
                    "type": "function",
                    "function": {"name": "echo", "description": "Echo", "parameters": {}},
                }
            ],
        )

    assert result.final_text == "hello"
    assert result.usage.total_tokens == 5
    assert captured["authorization"] == "Bearer secret-key"
    assert captured["payload"]["tool_choice"] == "auto"


async def test_client_serializes_tool_result_messages() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["messages"] = json.loads(request.content)["messages"]
        return make_response()

    call = ToolCall(id="call-1", name="calculator", arguments_json='{"expression":"1+1"}')
    messages = [
        Message(session_id="s", role="assistant", tool_calls=[call]),
        Message(session_id="s", role="tool", content="2", tool_call_id="call-1"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAICompatibleClient(
            http_client,
            base_url="https://llm.example/v1",
            api_key="key",
            model="model",
        )
        await client.complete(messages, [])

    assert captured["messages"][0]["tool_calls"][0]["function"]["name"] == "calculator"
    assert captured["messages"][1]["tool_call_id"] == "call-1"


def test_parser_handles_multiple_tool_calls_and_dict_arguments() -> None:
    result = OpenAICompatibleClient.parse_response(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "a",
                                "function": {"name": "calculator", "arguments": '{"x":1}'},
                            },
                            {
                                "id": "b",
                                "function": {"name": "search", "arguments": {"query": "agent"}},
                            },
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
    )
    assert [call.name for call in result.tool_calls] == ["calculator", "search"]
    assert json.loads(result.tool_calls[1].arguments_json) == {"query": "agent"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"tool_calls": "bad"}}]},
    ],
)
def test_parser_rejects_malformed_responses(payload) -> None:
    with pytest.raises(LLMProtocolError):
        OpenAICompatibleClient.parse_response(payload)


async def test_client_maps_http_status_and_timeout() -> None:
    def status_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "do not expose"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(status_handler)) as http_client:
        client = OpenAICompatibleClient(
            http_client, base_url="https://x/v1", api_key="k", model="m"
        )
        with pytest.raises(LLMHTTPError) as error:
            await client.complete([Message(session_id="s", role="user", content="x")], [])
        assert error.value.status_code == 429

    def timeout_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as http_client:
        client = OpenAICompatibleClient(
            http_client, base_url="https://x/v1", api_key="k", model="m"
        )
        with pytest.raises(LLMTimeoutError):
            await client.complete([Message(session_id="s", role="user", content="x")], [])


async def test_tools_are_omitted_when_disabled() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return make_response()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAICompatibleClient(
            http_client, base_url="https://x/v1", api_key="k", model="m"
        )
        await client.complete(
            [Message(session_id="s", role="user", content="summarize")],
            [{"type": "function"}],
            allow_tools=False,
        )
    assert "tools" not in captured
    assert "tool_choice" not in captured

