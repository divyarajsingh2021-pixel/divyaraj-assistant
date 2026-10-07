"""Environment-backed application settings."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

DEFAULT_ALLOWED_APPS = {
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "notepad": "notepad.exe",
}


class Settings(BaseModel):
    """Validated runtime settings for Divyaraj Assistant."""

    app_name: str = "Divyaraj Assistant"
    log_level: str = "INFO"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    data_dir: Path = Path("data")
    allowed_apps: dict[str, str] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_APPS.copy()
    )

    @property
    def database_path(self) -> Path:
        """Return the SQLite database path inside the configured data folder."""
        return self.data_dir / "divyaraj.db"


def load_settings() -> Settings:
    """Load settings from environment variables and an optional local .env file."""
    load_dotenv()
    allowed_apps = os.environ.get("ALLOWED_APPS")
    if allowed_apps:
        try:
            parsed_allowed_apps = json.loads(allowed_apps)
        except json.JSONDecodeError as error:
            raise ValueError("ALLOWED_APPS must be a valid JSON object.") from error
        if not isinstance(parsed_allowed_apps, dict) or not all(
            isinstance(name, str) for name in parsed_allowed_apps
        ):
            raise ValueError("ALLOWED_APPS must be a JSON object with string keys.")
    else:
        parsed_allowed_apps = DEFAULT_ALLOWED_APPS
    return Settings(
        app_name=os.environ.get("APP_NAME", "Divyaraj Assistant"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        llm_provider=os.environ.get("LLM_PROVIDER", "ollama"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
        data_dir=Path(os.environ.get("DATA_DIR", "data")),
        allowed_apps={
            name.casefold(): executable
            for name, executable in parsed_allowed_apps.items()
        },
    )
