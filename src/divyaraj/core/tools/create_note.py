"""Tool for saving personal notes."""

from divyaraj.core.memory import Memory
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class CreateNoteTool(Tool):
    """Save a title and content to the local notes database."""

    name = "create_note"
    description = "Save a note with a short title and its full content."
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short note title."},
            "content": {"type": "string", "description": "Note content."},
        },
        "required": ["title", "content"],
        "additionalProperties": False,
    }

    def __init__(self, memory: Memory | None = None) -> None:
        """Use supplied memory or open the configured SQLite database at run time."""
        self._memory = memory

    def run(self, arguments: dict[str, object]) -> str:
        """Create the note and return its ID and title."""
        title = arguments.get("title")
        content = arguments.get("content")
        if not isinstance(title, str) or not isinstance(content, str):
            raise ValueError("create_note requires string title and content.")
        note = (self._memory or Memory()).create_note(title, content)
        return f"Created note #{note.id}: {note.title}"
