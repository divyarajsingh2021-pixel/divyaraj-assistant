"""Tests for environment-backed settings."""

import pytest

from divyaraj.config import load_settings, user_data_directory


def test_load_settings_reads_environment(monkeypatch) -> None:
    """Environment values override the defaults."""
    monkeypatch.setenv("APP_NAME", "Test Assistant")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    monkeypatch.setenv("WHISPER_MODEL", "base")
    monkeypatch.setenv("VOICE_ENABLED", "false")
    monkeypatch.setenv("GLOBAL_HOTKEY", "alt+space")
    monkeypatch.setenv("START_WITH_WINDOWS", "true")

    settings = load_settings()

    assert settings.app_name == "Test Assistant"
    assert settings.ollama_model == "test-model"
    assert settings.whisper_model == "base"
    assert not settings.voice_enabled
    assert settings.global_hotkey == "alt+space"
    assert settings.start_with_windows


def test_load_settings_uses_defaults(monkeypatch) -> None:
    """Unset values receive safe local defaults."""
    monkeypatch.setattr("divyaraj.config.load_dotenv", lambda *args, **kwargs: None)
    for name in (
        "APP_NAME",
        "LOG_LEVEL",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "WHISPER_MODEL",
        "VOICE_ENABLED",
        "GLOBAL_HOTKEY",
        "START_WITH_WINDOWS",
        "DATA_DIR",
        "ALLOWED_APPS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.app_name == "Divyaraj Assistant"
    assert settings.llm_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:1.5b"
    assert settings.whisper_model == "base"
    assert settings.global_hotkey == "ctrl+space"
    assert not settings.start_with_windows
    assert settings.allowed_apps == {
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "notepad": "notepad.exe",
    }


def test_default_data_directory_uses_appdata(monkeypatch, tmp_path) -> None:
    """Installed app defaults and model paths stay inside the user's profile."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("PIPER_MODEL_PATH", raising=False)
    monkeypatch.setattr("divyaraj.config.load_dotenv", lambda *args, **kwargs: None)

    settings = load_settings()

    expected_directory = tmp_path / "Roaming" / "Divyaraj"
    assert user_data_directory() == expected_directory
    assert settings.data_dir == expected_directory
    assert settings.database_path == expected_directory / "divyaraj.db"
    assert settings.whisper_download_dir == expected_directory / "models" / "whisper"
    assert settings.piper_model_path == (
        expected_directory / "models" / "en_US-lessac-medium.onnx"
    )


def test_relative_data_dir_stays_under_appdata(monkeypatch, tmp_path) -> None:
    """Relative data overrides cannot resolve into a protected install directory."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("DATA_DIR", "assistant-data")
    monkeypatch.delenv("PIPER_MODEL_PATH", raising=False)
    monkeypatch.setattr("divyaraj.config.load_dotenv", lambda *args, **kwargs: None)

    settings = load_settings()

    assert settings.data_dir == tmp_path / "Roaming" / "Divyaraj" / "assistant-data"
    assert settings.settings_path == tmp_path / "Roaming" / "Divyaraj" / ".env"


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
