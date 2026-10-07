"""Tests for environment-backed settings."""

from divyaraj.config import load_settings


def test_load_settings_reads_environment(monkeypatch) -> None:
    """Environment values override the defaults."""
    monkeypatch.setenv("APP_NAME", "Test Assistant")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    settings = load_settings()

    assert settings.app_name == "Test Assistant"
    assert settings.ollama_model == "test-model"


def test_load_settings_uses_defaults(monkeypatch) -> None:
    """Unset values receive safe local defaults."""
    for name in (
        "APP_NAME",
        "LOG_LEVEL",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.app_name == "Divyaraj Assistant"
    assert settings.llm_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
