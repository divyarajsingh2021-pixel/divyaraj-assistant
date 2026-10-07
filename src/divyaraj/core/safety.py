"""Safety checks for tool execution."""

from collections.abc import Callable

from divyaraj.core.tools.base import Tool

ConfirmationCallback = Callable[[Tool], bool]


class ConfirmationRequiredError(PermissionError):
    """Raised when a risky tool is requested without explicit confirmation."""


def ensure_confirmation(
    tool: Tool,
    confirm: ConfirmationCallback | None = None,
) -> None:
    """Ask the provided callback to approve risky tools before execution."""
    if not tool.risky:
        return
    if confirm is None or not confirm(tool):
        raise ConfirmationRequiredError(
            f"Tool '{tool.name}' is risky and requires explicit confirmation."
        )
