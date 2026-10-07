"""Interface and Ollama implementation for language-model conversations."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import ollama
from ollama import ChatResponse

from divyaraj.config import Settings, load_settings
from divyaraj.core.tools.base import Tool


@dataclass(frozen=True)
class ToolCall:
    """A tool requested by a language model."""

    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class LLMResponse:
    """Normalized language-model response."""

    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    raw_assistant_message: dict[str, object] = field(default_factory=dict)


class LLM(Protocol):
    """Swappable interface used by the agent."""

    def chat(
        self,
        messages: Sequence[dict[str, object]],
        tools: Sequence[dict[str, object]],
    ) -> LLMResponse:
        """Return a model response, optionally containing tool requests."""


class OllamaUnavailableError(ConnectionError):
    """Raised when the configured local Ollama service cannot be reached."""


class OllamaClient:
    """Use Ollama's chat API and native function-calling support."""

    def __init__(
        self,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        """Create an Ollama client using configured host and model."""
        configuration = settings or load_settings()
        self.model = model or configuration.ollama_model
        self._client = ollama.Client(host=configuration.ollama_base_url)

    def chat(
        self,
        messages: Sequence[dict[str, object]],
        tools: Sequence[dict[str, object]],
    ) -> LLMResponse:
        """Send chat history and callable tool schemas to Ollama."""
        try:
            response = self._client.chat(
                model=self.model,
                messages=list(messages),
                tools=list(tools),
            )
        except (
            httpx.HTTPError,
            ollama.ResponseError,
            ConnectionError,
            OSError,
        ) as error:
            raise OllamaUnavailableError(
                "Could not reach Ollama. Start Ollama and ensure the configured "
                f"model '{self.model}' is available."
            ) from error
        return _normalize_response(response)


def tools_to_schema(tools: Sequence[Tool]) -> list[dict[str, object]]:
    """Convert registered tools to Ollama's function-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema,
            },
        }
        for tool in tools
    ]


def _normalize_response(response: ChatResponse) -> LLMResponse:
    """Convert the Ollama SDK response into the provider-neutral format."""
    assistant_message = response.message.model_dump(exclude_none=True)
    tool_calls = tuple(
        ToolCall(
            name=tool_call.function.name,
            arguments=dict(tool_call.function.arguments),
        )
        for tool_call in response.message.tool_calls or []
    )
    return LLMResponse(
        content=response.message.content or "",
        tool_calls=tool_calls,
        raw_assistant_message=assistant_message,
    )
