"""Allowlisted desktop application launcher."""

import subprocess

from divyaraj.config import load_settings
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import register


@register
class OpenAppTool(Tool):
    """Open an explicitly allowlisted application."""

    name = "open_app"
    description = "Open an application from the configured app allowlist."
    risky = True
    args_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": "Allowlisted application name, e.g. notepad.",
            }
        },
        "required": ["app"],
        "additionalProperties": False,
    }

    def run(self, arguments: dict[str, object]) -> str:
        """Launch an allowlisted application without invoking a shell."""
        app = arguments.get("app")
        if not isinstance(app, str) or not app.strip():
            raise ValueError("open_app requires an application name.")
        app_name = app.strip().casefold()
        allowed_apps = load_settings().allowed_apps
        executable = allowed_apps.get(app_name)
        if executable is None:
            raise ValueError(
                f"'{app_name}' is not allowlisted. Configured apps: "
                f"{', '.join(sorted(allowed_apps)) or 'none'}."
            )
        subprocess.Popen([executable], shell=False)
        return f"Opened {app_name}."
