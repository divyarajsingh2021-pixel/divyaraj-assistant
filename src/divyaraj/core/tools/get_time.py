"""Local clock tool."""

from datetime import datetime

from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class GetTimeTool(Tool):
    """Report the local system time."""

    name = "get_time"
    description = "Get the current local date and time."
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def run(self, arguments: dict[str, object]) -> str:
        """Return the local date and time in ISO 8601 format."""
        if arguments:
            raise ValueError("The get_time tool does not accept arguments.")
        return datetime.now().astimezone().isoformat(timespec="seconds")
