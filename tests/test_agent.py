"""Tests for the tool-using agent loop."""

from pathlib import Path

from divyaraj.core.agent import Agent
from divyaraj.core.llm import LLMResponse, ToolCall
from divyaraj.core.memory import Memory
from divyaraj.core.tools.base import Tool


class MockLLM:
    """Return scripted answers and capture the messages sent by the agent."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls: list[list[dict[str, object]]] = []

    def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> LLMResponse:
        self.calls.append(list(messages))
        return self.responses.pop(0)


class EchoTool(Tool):
    """Safe tool for agent-loop tests."""

    name = "echo_for_agent_test"
    description = "Return the provided text."
    args_schema: dict[str, object] = {"type": "object"}

    def __init__(self) -> None:
        self.runs = 0

    def run(self, arguments: dict[str, object]) -> str:
        self.runs += 1
        return str(arguments["text"])


class RiskyAgentTestTool(EchoTool):
    """Risky tool for confirmation tests."""

    name = "risky_for_agent_test"
    risky = True


class WebSearchTestTool(EchoTool):
    """Tool named like web search for textual instruction recovery tests."""

    name = "web_search"

    def run(self, arguments: dict[str, object]) -> str:
        self.runs += 1
        return str(arguments["query"])


class FixedTimeTool(Tool):
    """Clock tool that returns a known value for guard tests."""

    name = "get_time"
    description = "Return a fixed test time."
    args_schema: dict[str, object] = {"type": "object"}

    def __init__(self) -> None:
        self.runs = 0

    def run(self, arguments: dict[str, object]) -> str:
        self.runs += 1
        return "2026-10-11T21:18:00+05:30"


def _memory(tmp_path: Path) -> Memory:
    """Return isolated SQLite memory for one test."""
    return Memory(tmp_path / "agent.sqlite")


def test_agent_returns_final_model_reply_and_persists_turn(tmp_path: Path) -> None:
    """A plain user turn is sent to the model and stored in memory."""
    llm = MockLLM([LLMResponse(content="Hello there.")])
    memory = _memory(tmp_path)
    agent = Agent(llm=llm, memory=memory, tools=[])

    assert agent.respond(" hello ") == "Hello there."
    assert [(item.role, item.content) for item in memory.history()] == [
        ("user", "hello"),
        ("assistant", "Hello there."),
    ]


def test_agent_executes_tool_then_sends_result_back_to_model(
    tmp_path: Path,
) -> None:
    """Tool output is added to the next model request before final response."""
    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=(
                    ToolCall(
                        name="echo_for_agent_test",
                        arguments={"text": "tool result"},
                    ),
                ),
            ),
            LLMResponse(content="The tool said tool result."),
        ]
    )
    tool = EchoTool()
    agent = Agent(llm=llm, memory=_memory(tmp_path), tools=[tool])

    assert agent.respond("use the tool") == "The tool said tool result."
    assert tool.runs == 1
    assert llm.calls[1][-1] == {
        "role": "tool",
        "name": "echo_for_agent_test",
        "content": "tool result",
    }


def test_agent_recovers_function_instruction_and_runs_tool(tmp_path: Path) -> None:
    """The agent executes a named tool instead of asking the user to call it."""
    llm = MockLLM(
        [
            LLMResponse(content="Please call the function web_search."),
            LLMResponse(content="Here are the results."),
        ]
    )
    tool = WebSearchTestTool()
    agent = Agent(llm=llm, memory=_memory(tmp_path), tools=[tool])

    assert agent.respond("Find recent Python news.") == "Here are the results."
    assert tool.runs == 1
    assert llm.calls[0][0]["role"] == "system"
    system_prompt = str(llm.calls[0][0]["content"])
    assert "ALWAYS call get_time" in system_prompt
    assert "ALWAYS call web_search" in system_prompt
    assert llm.calls[1][-1] == {
        "role": "tool",
        "name": "web_search",
        "content": "Find recent Python news.",
    }


def test_agent_replaces_unverified_time_or_date_with_clock_tool(
    tmp_path: Path,
) -> None:
    """A final model answer containing a date is discarded without tool use."""
    llm = MockLLM([LLMResponse(content="It is Sunday, 11 October at 9:18 PM.")])
    clock = FixedTimeTool()
    agent = Agent(llm=llm, memory=_memory(tmp_path), tools=[clock])

    assert agent.respond("Tell me something.") == "2026-10-11T21:18:00+05:30"
    assert clock.runs == 1
    assert len(llm.calls) == 1


def test_agent_stops_after_five_tool_steps(tmp_path: Path) -> None:
    """A tool-request loop cannot run more than five times per user turn."""
    llm = MockLLM(
        [
            *[
                LLMResponse(
                    content="",
                    tool_calls=(
                        ToolCall(
                            name="echo_for_agent_test",
                            arguments={"text": "again"},
                        ),
                    ),
                )
                for _ in range(6)
            ]
        ]
    )
    tool = EchoTool()
    agent = Agent(llm=llm, memory=_memory(tmp_path), tools=[tool])

    response = agent.respond("loop")

    assert "stopped after 5 tool steps" in response
    assert tool.runs == 5


def test_risky_tool_runs_when_confirmation_approved(tmp_path: Path) -> None:
    """An approved risky tool request is executed."""
    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=(ToolCall("risky_for_agent_test", {"text": "done"}),),
            ),
            LLMResponse("Action completed."),
        ]
    )
    tool = RiskyAgentTestTool()
    confirmations: list[str] = []

    def approve(requested: Tool) -> bool:
        confirmations.append(requested.name)
        return True

    agent = Agent(
        llm=llm,
        memory=_memory(tmp_path),
        tools=[tool],
        confirmation_callback=approve,
    )

    assert agent.respond("open it") == "Action completed."
    assert confirmations == ["risky_for_agent_test"]
    assert tool.runs == 1


def test_risky_tool_is_not_run_when_confirmation_denied(tmp_path: Path) -> None:
    """A denied risky request is sent back as cancelled without running it."""
    llm = MockLLM(
        [
            LLMResponse(
                content="",
                tool_calls=(ToolCall("risky_for_agent_test", {"text": "done"}),),
            ),
            LLMResponse("I cancelled that action."),
        ]
    )
    tool = RiskyAgentTestTool()
    agent = Agent(
        llm=llm,
        memory=_memory(tmp_path),
        tools=[tool],
        confirmation_callback=lambda requested: False,
    )

    assert agent.respond("open it") == "I cancelled that action."
    assert tool.runs == 0
    assert "did not approve" in str(llm.calls[1][-1]["content"])
