"""Tool for searching personal notes."""

from divyaraj.core.memory import Memory
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class SearchNotesTool(Tool):
    """Search note titles and content in local memory."""

    name = "search_notes"
    description = "Search saved notes by matching text in their title or content."
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to search for."}
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, memory: Memory | None = None) -> None:
        """Use supplied memory or open the configured SQLite database at run time."""
        self._memory = memory

    def run(self, arguments: dict[str, object]) -> str:
        """Return matching notes or a clear no-results message."""
        query = arguments.get("query")
        if not isinstance(query, str):
            raise ValueError("search_notes requires a string query.")
        notes = (self._memory or Memory()).search_notes(query)
        if not notes:
            return "No notes matched that search."
        return "\n".join(f"#{note.id} {note.title}: {note.content}" for note in notes)
