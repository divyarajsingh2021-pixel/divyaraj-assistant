"""Manage the optional current-user Windows Startup entry."""

from __future__ import annotations

import os
import sys
from pathlib import Path

STARTUP_SCRIPT_NAME = "Divyaraj Assistant.cmd"


def current_user_startup_folder() -> Path:
    """Return the current Windows user's Startup folder."""
    if os.name != "nt":
        raise OSError("Starting with Windows is only available on Windows.")
    app_data = os.environ.get("APPDATA")
    if not app_data:
        raise OSError("The current user's APPDATA folder could not be located.")
    return Path(app_data) / "Microsoft/Windows/Start Menu/Programs/Startup"


def set_start_with_windows(
    enabled: bool,
    *,
    startup_folder: Path | None = None,
    executable: Path | None = None,
    working_directory: Path | None = None,
) -> Path:
    """Create or remove a current-user Startup command without admin access."""
    folder = startup_folder or current_user_startup_folder()
    script = folder / STARTUP_SCRIPT_NAME
    if not enabled:
        script.unlink(missing_ok=True)
        return script

    python_executable = executable or Path(sys.executable)
    project_directory = working_directory or (
        python_executable.parent if getattr(sys, "frozen", False) else Path.cwd()
    )
    folder.mkdir(parents=True, exist_ok=True)
    launch_command = (
        f'"{python_executable}"'
        if getattr(sys, "frozen", False)
        else f'"{python_executable}" -m divyaraj --gui'
    )
    script.write_text(
        f'@echo off\r\ncd /d "{project_directory}"\r\n{launch_command}\r\n',
        encoding="utf-8",
    )
    return script
