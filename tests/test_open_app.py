"""Tests for allowlisted application launching."""

from unittest.mock import Mock

import pytest

from divyaraj.config import Settings
from divyaraj.core.tools import open_app


def test_open_app_launches_only_the_configured_executable(monkeypatch) -> None:
    """Configured app identifiers are resolved without shell invocation."""
    monkeypatch.setattr(
        open_app,
        "load_settings",
        lambda: Settings(allowed_apps={"editor": "C:/Apps/editor.exe"}),
    )
    launch = Mock()
    monkeypatch.setattr(open_app.subprocess, "Popen", launch)

    assert open_app.OpenAppTool().run({"app": " Editor "}) == "Opened editor."
    launch.assert_called_once_with(["C:/Apps/editor.exe"], shell=False)


def test_open_app_rejects_unlisted_programs(monkeypatch) -> None:
    """An arbitrary executable is never passed to the process launcher."""
    monkeypatch.setattr(
        open_app,
        "load_settings",
        lambda: Settings(allowed_apps={"editor": "editor.exe"}),
    )
    launch = Mock()
    monkeypatch.setattr(open_app.subprocess, "Popen", launch)

    with pytest.raises(ValueError, match="not allowlisted"):
        open_app.OpenAppTool().run({"app": "cmd.exe"})
    launch.assert_not_called()
