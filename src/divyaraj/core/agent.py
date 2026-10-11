"""Agent loop coordinating conversation, tools, and safety."""

import sqlite3
from collections.abc import Sequence

from divyaraj.config import load_settings
from divyaraj.core.intent_router import (
    ToolIntent,
    detect_function_call_instruction,
    has_clock_time_or_date,
    has_function_call_instruction,
    route_intent,
)
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
SYSTEM_PROMPT = """You are Divyaraj, a careful personal assistant.
Strict tool-use rules:
- For the current time or date, ALWAYS call get_time. Never answer from memory or guess.
- For notes, ALWAYS call create_note, list_notes, or search_notes as appropriate.
- For web searches, ALWAYS call web_search. Never answer from memory or guess.
- For opening apps, ALWAYS call open_app. Never claim an app was opened without
  using it.
- Never tell the user to call, invoke, or run a function or tool themselves.
  You call tools.
- If a note lacks its content, ask the user what to save before creating it.
"""
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
        self.allowed_apps = load_settings().allowed_apps

    def respond(self, message: str) -> str:
        """Process a user turn, running no more than five tool calls."""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message must not be empty.")

        self.memory.add_user_message(normalized_message)
        intent = route_intent(normalized_message, self.allowed_apps)
        if intent is not None:
            if intent.clarification:
                self.memory.add_assistant_message(intent.clarification)
                return intent.clarification
            direct_result = self._run_tool(ToolCall(intent.tool_name, intent.arguments))
            self.memory.add_assistant_message(direct_result)
            return direct_result

        messages: list[dict[str, object]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        messages.extend(
            {"role": item.role, "content": item.content}
            for item in self.memory.history()
        )
        tool_schemas = tools_to_schema(self.tools)
        tool_steps = 0

        while True:
            response = self.llm.chat(messages, tool_schemas)
            if not response.tool_calls and has_function_call_instruction(
                response.content
            ):
                tool_name = detect_function_call_instruction(
                    response.content,
                    {tool.name for tool in self.tools},
                )
                if tool_name is None:
                    safe_reply = (
                        "I couldn't identify the right tool for that request. "
                        "Please rephrase what you'd like me to do."
                    )
                    self.memory.add_assistant_message(safe_reply)
                    return safe_reply
                if tool_steps >= MAX_TOOL_STEPS:
                    return self._finish_tool_limit()
                tool_call = _instruction_tool_call(
                    tool_name,
                    normalized_message,
                    route_intent(normalized_message, self.allowed_apps),
                )
                messages.append(
                    _assistant_message(
                        LLMResponse(content=response.content, tool_calls=(tool_call,))
                    )
                )
                tool_steps += 1
                result = self._run_tool(tool_call)
                messages.append({"role": "tool", "name": tool_name, "content": result})
                continue
            if not response.tool_calls:
                if tool_steps == 0 and has_clock_time_or_date(response.content):
                    clock_result = self._run_tool(ToolCall("get_time", {}))
                    self.memory.add_assistant_message(clock_result)
                    return clock_result
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


def _instruction_tool_call(
    tool_name: str,
    user_message: str,
    intent: ToolIntent | None,
) -> ToolCall:
    """Build arguments for a named textual instruction without inventing details."""
    if intent is not None and intent.tool_name == tool_name:
        return ToolCall(tool_name, dict(intent.arguments))
    if tool_name in {"get_time", "list_notes"}:
        return ToolCall(tool_name, {})
    if tool_name in {"web_search", "search_notes"}:
        return ToolCall(tool_name, {"query": user_message})
    if tool_name == "create_note":
        return ToolCall(tool_name, {"title": "Note", "content": user_message})
    if tool_name == "open_app":
        app = user_message.strip().removeprefix("open ").strip()
        return ToolCall(tool_name, {"app": app})
    return ToolCall(tool_name, {})
