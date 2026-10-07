"""Shared registry for tool classes."""

from importlib import import_module
from typing import TypeVar

from divyaraj.core.tools.base import Tool

TTool = TypeVar("TTool", bound=Tool)
_TOOLS: dict[str, Tool] = {}
_BUILTIN_TOOL_MODULES = (
    "create_note",
    "get_time",
    "list_notes",
    "open_app",
    "search_notes",
    "web_search",
)


def register(tool_class: type[TTool]) -> type[TTool]:
    """Register and return a no-argument tool class for decorator use."""
    tool = tool_class()
    if tool.name in _TOOLS:
        raise ValueError(f"A tool named '{tool.name}' is already registered.")
    _TOOLS[tool.name] = tool
    return tool_class


def get_tool(name: str) -> Tool:
    """Return a registered tool by name."""
    _load_builtin_tools()
    try:
        return _TOOLS[name]
    except KeyError as error:
        raise KeyError(f"Tool '{name}' is not registered.") from error


def get_registered_tools() -> tuple[Tool, ...]:
    """Load built-in tools and return a snapshot of registered instances."""
    _load_builtin_tools()
    return tuple(_TOOLS.values())


def _load_builtin_tools() -> None:
    """Import built-in modules once so their decorators register each tool."""
    for module_name in _BUILTIN_TOOL_MODULES:
        import_module(f"divyaraj.core.tools.{module_name}")
