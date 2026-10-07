"""Safety checks for tool execution."""

from divyaraj.core.tools.base import Tool


class ConfirmationRequiredError(PermissionError):
    """Raised when a risky tool is requested without explicit confirmation."""


def ensure_confirmation(tool: Tool, confirmed: bool = False) -> None:
    """Reject risky tool execution unless the user explicitly confirmed it."""
    if tool.risky and not confirmed:
        raise ConfirmationRequiredError(
            f"Tool '{tool.name}' is risky and requires explicit confirmation."
        )
