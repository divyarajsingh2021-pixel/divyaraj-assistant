"""Tests for the local clock tool."""

from datetime import datetime

import pytest

from divyaraj.core.tools.get_time import GetTimeTool


def test_get_time_returns_iso_local_datetime(monkeypatch) -> None:
    """The result is a local ISO timestamp with second precision."""
    expected = "2026-10-07T12:34:56+05:30"

    class FixedDateTime:
        @classmethod
        def now(cls) -> datetime:
            return datetime.fromisoformat(expected)

    monkeypatch.setattr("divyaraj.core.tools.get_time.datetime", FixedDateTime)

    assert GetTimeTool().run({}) == expected


def test_get_time_rejects_arguments() -> None:
    """Unexpected arguments are rejected instead of being ignored."""
    with pytest.raises(ValueError, match="does not accept arguments"):
        GetTimeTool().run({"unexpected": "value"})
