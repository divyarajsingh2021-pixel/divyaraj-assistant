"""Free web search tool powered by DuckDuckGo."""

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException

from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class WebSearchTool(Tool):
    """Search the public web and return up to three results."""

    name = "web_search"
    description = "Search the web and return the three most relevant results."
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search terms."}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def run(self, arguments: dict[str, object]) -> str:
        """Return up to three results with title, URL, and summary."""
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("web_search requires a non-empty query.")
        try:
            results = DDGS().text(query.strip(), max_results=3)
        except DuckDuckGoSearchException as error:
            raise RuntimeError(f"DuckDuckGo search failed: {error}") from error
        if not results:
            return "No web results were found."
        formatted = []
        for result in results[:3]:
            title = result.get("title", "Untitled result")
            url = result.get("href", "")
            body = result.get("body", "")
            formatted.append(f"{title}\n{url}\n{body}")
        return "\n\n".join(formatted)
