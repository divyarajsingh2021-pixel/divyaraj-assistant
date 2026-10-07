"""Tool for listing saved personal notes."""

from divyaraj.core.memory import Memory
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class ListNotesTool(Tool):
    """List saved notes from local memory."""

    name = "list_notes"
    description = "List all saved notes."
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def __init__(self, memory: Memory | None = None) -> None:
        """Use supplied memory or open the configured SQLite database at run time."""
        self._memory = memory

    def run(self, arguments: dict[str, object]) -> str:
        """Return saved notes as a compact readable list."""
        if arguments:
            raise ValueError("list_notes does not accept arguments.")
        notes = (self._memory or Memory()).list_notes()
        if not notes:
            return "There are no saved notes."
        return "\n".join(f"#{note.id} {note.title}: {note.content}" for note in notes)
