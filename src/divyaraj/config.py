"""Environment-backed application settings."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    """Validated runtime settings for Divyaraj Assistant."""

    app_name: str = "Divyaraj Assistant"
    log_level: str = "INFO"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"


def load_settings() -> Settings:
    """Load settings from environment variables and an optional local .env file."""
    load_dotenv()
    return Settings(
        app_name=os.environ.get("APP_NAME", "Divyaraj Assistant"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        llm_provider=os.environ.get("LLM_PROVIDER", "ollama"),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.2"),
    )
