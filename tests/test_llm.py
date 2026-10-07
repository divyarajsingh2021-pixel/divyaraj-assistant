"""Tests for the Ollama LLM adapter."""

from types import SimpleNamespace

import pytest

from divyaraj.config import Settings
from divyaraj.core.llm import OllamaClient, OllamaUnavailableError, tools_to_schema
from divyaraj.core.tools.base import Tool


class SchemaTool(Tool):
    """Tool used to verify provider-neutral schema conversion."""

    name = "schema_tool"
    description = "Test schema."
    args_schema: dict[str, object] = {"type": "object", "properties": {}}

    def run(self, arguments: dict[str, object]) -> str:
        return "unused"


def test_tools_are_converted_to_ollama_function_schema() -> None:
    """Ollama receives each tool's name, description, and argument schema."""
    schema = tools_to_schema([SchemaTool()])

    assert schema == [
        {
            "type": "function",
            "function": {
                "name": "schema_tool",
                "description": "Test schema.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_ollama_client_normalizes_response_and_uses_config() -> None:
    """Adapter passes configured host/model and exposes the tool request."""
    client = OllamaClient(Settings(ollama_base_url="http://example:11434"), "test")
    captured: dict[str, object] = {}
    raw_call = {
        "function": {
            "name": "schema_tool",
            "arguments": {"value": "from tool"},
        }
    }

    class FakeOllama:
        def chat(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="schema_tool",
                                arguments={"value": "from tool"},
                            )
                        )
                    ],
                    model_dump=lambda exclude_none: {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [raw_call],
                    },
                )
            )

    client._client = FakeOllama()
    result = client.chat([{"role": "user", "content": "hello"}], [])

    assert captured["model"] == "test"
    assert result.tool_calls[0].name == "schema_tool"
    assert result.tool_calls[0].arguments == {"value": "from tool"}
    assert result.raw_assistant_message["tool_calls"] == [raw_call]


def test_ollama_connection_error_is_friendly() -> None:
    """Connection failures produce an actionable domain-specific error."""
    client = OllamaClient(Settings(ollama_model="qwen2.5:3b"))

    class OfflineOllama:
        def chat(self, **kwargs: object) -> None:
            raise ConnectionRefusedError("connection refused")

    client._client = OfflineOllama()
    with pytest.raises(OllamaUnavailableError, match="Start Ollama"):
        client.chat([], [])
