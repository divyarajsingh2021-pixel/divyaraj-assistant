"""Tests for SQLite-backed note tools."""

from pathlib import Path

from divyaraj.core.memory import Memory
from divyaraj.core.tools.create_note import CreateNoteTool
from divyaraj.core.tools.list_notes import ListNotesTool
from divyaraj.core.tools.search_notes import SearchNotesTool


def test_note_tools_create_list_and_search(tmp_path: Path) -> None:
    """The three tools share the same injected memory database."""
    memory = Memory(tmp_path / "notes.sqlite")
    create = CreateNoteTool(memory)
    list_tool = ListNotesTool(memory)
    search = SearchNotesTool(memory)

    assert create.run({"title": "Plan", "content": "Walk the dog"}) == (
        "Created note #1: Plan"
    )
    assert "Plan: Walk the dog" in list_tool.run({})
    assert "Plan: Walk the dog" in search.run({"query": "dog"})
