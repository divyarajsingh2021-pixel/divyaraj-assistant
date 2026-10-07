"""Shared registry for tool classes."""

from typing import TypeVar

from divyaraj.core.tools.base import Tool

TTool = TypeVar("TTool", bound=Tool)
_TOOLS: dict[str, Tool] = {}


def register(tool_class: type[TTool]) -> type[TTool]:
    """Register and return a no-argument tool class for decorator use."""
    tool = tool_class()
    if tool.name in _TOOLS:
        raise ValueError(f"A tool named '{tool.name}' is already registered.")
    _TOOLS[tool.name] = tool
    return tool_class


def get_tool(name: str) -> Tool:
    """Return a registered tool by name."""
    try:
        return _TOOLS[name]
    except KeyError as error:
        raise KeyError(f"Tool '{name}' is not registered.") from error


def get_registered_tools() -> tuple[Tool, ...]:
    """Return a snapshot of registered tool instances."""
    return tuple(_TOOLS.values())
