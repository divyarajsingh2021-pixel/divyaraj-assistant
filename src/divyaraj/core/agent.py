"""Agent loop coordinating conversation, tools, and safety."""

import sqlite3
from collections.abc import Sequence

from divyaraj.core.llm import LLM, LLMResponse, OllamaClient, ToolCall, tools_to_schema
from divyaraj.core.memory import Memory
from divyaraj.core.safety import (
    ConfirmationCallback,
    ConfirmationRequiredError,
    ensure_confirmation,
)
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import get_registered_tools

MAX_TOOL_STEPS = 5
_TOOL_FAILURES = (
    KeyError,
    OSError,
    RuntimeError,
    sqlite3.Error,
    TypeError,
    ValueError,
)


class Agent:
    """Run user turns through a language model and available tools."""

    def __init__(
        self,
        llm: LLM | None = None,
        memory: Memory | None = None,
        tools: Sequence[Tool] | None = None,
        confirmation_callback: ConfirmationCallback | None = None,
    ) -> None:
        """Set up the provider, SQLite memory, tools, and confirmation callback."""
        self.llm = llm or OllamaClient()
        self.memory = memory or Memory()
        self.tools = tuple(tools) if tools is not None else get_registered_tools()
        self.confirmation_callback = confirmation_callback

    def respond(self, message: str) -> str:
        """Process a user turn, running no more than five tool calls."""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message must not be empty.")

        self.memory.add_user_message(normalized_message)
        messages: list[dict[str, object]] = [
            {"role": item.role, "content": item.content}
            for item in self.memory.history()
        ]
        tool_schemas = tools_to_schema(self.tools)
        tool_steps = 0

        while True:
            response = self.llm.chat(messages, tool_schemas)
            if not response.tool_calls:
                self.memory.add_assistant_message(response.content)
                return response.content
            if tool_steps >= MAX_TOOL_STEPS:
                return self._finish_tool_limit()

            messages.append(_assistant_message(response))
            for tool_call in response.tool_calls:
                if tool_steps >= MAX_TOOL_STEPS:
                    return self._finish_tool_limit()
                tool_steps += 1
                result = self._run_tool(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "name": tool_call.name,
                        "content": result,
                    }
                )

    def _run_tool(self, tool_call: ToolCall) -> str:
        """Safely execute one tool request and report failures to the model."""
        tools_by_name = {tool.name: tool for tool in self.tools}
        try:
            tool = tools_by_name[tool_call.name]
            ensure_confirmation(tool, self.confirmation_callback)
            return tool.run(tool_call.arguments)
        except ConfirmationRequiredError:
            return "Action cancelled: the user did not approve this tool."
        except _TOOL_FAILURES as error:
            return f"Tool execution failed: {error}"

    def _finish_tool_limit(self) -> str:
        """Persist and return a clear response when another tool call is requested."""
        response = (
            "I stopped after 5 tool steps to avoid an infinite tool-calling loop."
        )
        self.memory.add_assistant_message(response)
        return response


def _assistant_message(response: LLMResponse) -> dict[str, object]:
    """Preserve the provider's tool-call payload for the next chat turn."""
    if response.raw_assistant_message:
        return dict(response.raw_assistant_message)
    calls = [
        {
            "function": {
                "name": call.name,
                "arguments": call.arguments,
            }
        }
        for call in response.tool_calls
    ]
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": calls,
    }
