"""Tests for tool registration."""

import pytest

from divyaraj.core.tools import Tool, get_registered_tools, get_tool, register


def test_register_decorator_stores_tool_class() -> None:
    """A decorated tool class is instantiated and can be retrieved."""

    @register
    class ExampleRegistryTestTool(Tool):
        name = "example_registry_test"
        description = "A tool used to test the registry."
        args_schema: dict[str, object] = {
            "type": "object",
            "properties": {},
        }

        def run(self, arguments: dict[str, object]) -> str:
            return "ok"

    tool = get_tool("example_registry_test")

    assert isinstance(tool, ExampleRegistryTestTool)
    assert tool.run({}) == "ok"
    assert tool in get_registered_tools()


def test_duplicate_tool_names_are_rejected() -> None:
    """Registering a second tool with the same name fails clearly."""

    @register
    class OriginalDuplicateNameTestTool(Tool):
        name = "duplicate_registry_test"
        description = "Original."
        args_schema: dict[str, object] = {"type": "object"}

        def run(self, arguments: dict[str, object]) -> str:
            return "original"

    class DuplicateNameTestTool(Tool):
        name = "duplicate_registry_test"
        description = "Duplicate."
        args_schema: dict[str, object] = {"type": "object"}

        def run(self, arguments: dict[str, object]) -> str:
            return "duplicate"

    with pytest.raises(ValueError, match="already registered"):
        register(DuplicateNameTestTool)

    assert get_tool("duplicate_registry_test").run({}) == "original"


def test_unknown_tool_raises_clear_error() -> None:
    """A lookup for an unknown tool reports its name."""
    with pytest.raises(KeyError, match="not registered"):
        get_tool("missing_registry_test")


def test_builtin_tools_are_registered() -> None:
    """All built-in tools are automatically loaded and retrievable."""
    tools = get_registered_tools()
    registered_names = {tool.name for tool in tools}
    expected_names = {
        "create_note",
        "get_time",
        "list_notes",
        "open_app",
        "search_notes",
        "web_search",
    }
    assert expected_names.issubset(registered_names)
    for name in expected_names:
        assert get_tool(name).name == name

