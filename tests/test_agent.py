"""Tests for conversation orchestration."""

import pytest

from divyaraj.core.agent import Agent
from divyaraj.core.llm import LLMClient
from divyaraj.core.memory import Memory


def test_agent_records_exchange_and_returns_response() -> None:
    """Agent stores normalized input and generated response."""
    memory = Memory()
    agent = Agent(llm=LLMClient(), memory=memory)

    response = agent.respond("  hello  ")

    assert response == "I heard you: hello"
    assert [(message.role, message.content) for message in memory.history()] == [
        ("user", "hello"),
        ("assistant", "I heard you: hello"),
    ]


def test_agent_rejects_empty_input() -> None:
    """Blank messages are not passed into the LLM."""
    with pytest.raises(ValueError, match="must not be empty"):
        Agent().respond("  ")
