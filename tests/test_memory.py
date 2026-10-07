"""Tests for SQLite-backed history and notes."""

from pathlib import Path

from divyaraj.core.memory import Memory


def test_history_persists_between_memory_instances(tmp_path: Path) -> None:
    """A reopened memory database retains ordered user and assistant messages."""
    database = tmp_path / "nested" / "conversation.sqlite"
    memory = Memory(database)
    memory.add_user_message("hello")
    memory.add_assistant_message("hi")

    reopened_memory = Memory(database)

    assert [(item.role, item.content) for item in reopened_memory.history()] == [
        ("user", "hello"),
        ("assistant", "hi"),
    ]


def test_notes_can_be_created_listed_and_searched(tmp_path: Path) -> None:
    """Notes persist and search matches either title or content."""
    memory = Memory(tmp_path / "notes.sqlite")
    created = memory.create_note("Shopping", "Buy ripe mangoes")

    assert memory.list_notes() == (created,)
    assert memory.search_notes("ripe") == (created,)
    assert memory.search_notes("shopping") == (created,)
    assert memory.search_notes("missing") == ()


def test_search_treats_wildcards_as_literal_text(tmp_path: Path) -> None:
    """SQL wildcard characters in queries are escaped."""
    memory = Memory(tmp_path / "literal-search.sqlite")
    note = memory.create_note("Percent", "A 100% complete task")
    memory.create_note("Other", "A 100X complete task")

    assert memory.search_notes("100%") == (note,)
