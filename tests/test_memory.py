"""Tests for in-process conversation memory."""

from divyaraj.core.memory import Memory


def test_history_is_an_immutable_snapshot() -> None:
    """Later additions do not mutate a previously returned history."""
    memory = Memory()
    memory.add_user_message("hello")
    snapshot = memory.history()

    memory.add_assistant_message("hi")

    assert len(snapshot) == 1
    assert len(memory.history()) == 2
