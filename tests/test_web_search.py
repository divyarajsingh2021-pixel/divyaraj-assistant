"""Tests for the DuckDuckGo web-search tool."""

import pytest
from duckduckgo_search.exceptions import DuckDuckGoSearchException

from divyaraj.core.tools import web_search


def test_web_search_returns_at_most_three_results(monkeypatch) -> None:
    """The tool calls DuckDuckGo with the requested query and limits output."""
    captured: dict[str, object] = {}

    class FakeDDGS:
        def text(self, query: str, max_results: int) -> list[dict[str, str]]:
            captured["query"] = query
            captured["max_results"] = max_results
            return [
                {
                    "title": f"Result {index}",
                    "href": f"https://example/{index}",
                    "body": "summary",
                }
                for index in range(5)
            ]

    monkeypatch.setattr(web_search, "DDGS", FakeDDGS)

    result = web_search.WebSearchTool().run({"query": "  python  "})

    assert captured == {"query": "python", "max_results": 3}
    assert result.count("https://example/") == 3
    assert "Result 2" in result
    assert "Result 3" not in result


def test_web_search_rejects_empty_query() -> None:
    """Blank search requests fail validation."""
    with pytest.raises(ValueError, match="non-empty query"):
        web_search.WebSearchTool().run({"query": "  "})


def test_web_search_reports_service_failures(monkeypatch) -> None:
    """Search provider failures are surfaced with actionable context."""

    class OfflineDDGS:
        def text(self, query: str, max_results: int) -> list[dict[str, str]]:
            raise DuckDuckGoSearchException("offline")

    monkeypatch.setattr(web_search, "DDGS", OfflineDDGS)

    with pytest.raises(RuntimeError, match="DuckDuckGo search failed"):
        web_search.WebSearchTool().run({"query": "news"})
