"""Tests for environment-backed settings."""

import pytest

from divyaraj.config import load_settings


def test_load_settings_reads_environment(monkeypatch) -> None:
    """Environment values override the defaults."""
    monkeypatch.setenv("APP_NAME", "Test Assistant")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    monkeypatch.setenv("WHISPER_MODEL", "base")
    monkeypatch.setenv("VOICE_ENABLED", "false")

    settings = load_settings()

    assert settings.app_name == "Test Assistant"
    assert settings.ollama_model == "test-model"
    assert settings.whisper_model == "base"
    assert not settings.voice_enabled


def test_load_settings_uses_defaults(monkeypatch) -> None:
    """Unset values receive safe local defaults."""
    monkeypatch.setattr("divyaraj.config.load_dotenv", lambda: None)
    for name in (
        "APP_NAME",
        "LOG_LEVEL",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "WHISPER_MODEL",
        "VOICE_ENABLED",
        "DATA_DIR",
        "ALLOWED_APPS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.app_name == "Divyaraj Assistant"
    assert settings.llm_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:3b"
    assert settings.whisper_model == "base"
    assert settings.allowed_apps == {
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "notepad": "notepad.exe",
    }


def test_load_settings_parses_app_allowlist(monkeypatch) -> None:
    """Allowed application names map to configured executable paths."""
    monkeypatch.setenv("ALLOWED_APPS", '{"Editor":"C:/Tools/editor.exe"}')

    settings = load_settings()

    assert settings.allowed_apps == {"editor": "C:/Tools/editor.exe"}


def test_load_settings_rejects_invalid_app_allowlist(monkeypatch) -> None:
    """Malformed allowlist configuration fails with a clear message."""
    monkeypatch.setenv("ALLOWED_APPS", '["notepad"]')

    with pytest.raises(ValueError, match="JSON object"):
        load_settings()
