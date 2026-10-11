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
    whisper_model: str = "base"
    stt_compute_type: str = "int8"
    voice_enabled: bool = True
    global_hotkey: str = "ctrl+space"
    start_with_windows: bool = False
    piper_model_path: Path = Path("models/en_US-lessac-medium.onnx")
    speech_max_characters: int = 240

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
        whisper_model=os.environ.get("WHISPER_MODEL", "base"),
        stt_compute_type=os.environ.get("STT_COMPUTE_TYPE", "int8"),
        voice_enabled=os.environ.get("VOICE_ENABLED", "true").casefold()
        in {"1", "true", "yes", "on"},
        global_hotkey=os.environ.get("GLOBAL_HOTKEY", "ctrl+space"),
        start_with_windows=os.environ.get("START_WITH_WINDOWS", "false").casefold()
        in {"1", "true", "yes", "on"},
        piper_model_path=Path(
            os.environ.get("PIPER_MODEL_PATH", "models/en_US-lessac-medium.onnx")
        ),
        speech_max_characters=int(os.environ.get("SPEECH_MAX_CHARACTERS", "240")),
    )
