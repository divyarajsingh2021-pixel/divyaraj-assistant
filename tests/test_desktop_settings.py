"""Tests for persistence of desktop preferences."""

from pathlib import Path

import pytest
from dotenv import dotenv_values

from divyaraj.ui_desktop.settings import save_desktop_settings


def test_save_desktop_settings_writes_expected_environment_keys(
    tmp_path: Path,
) -> None:
    """Model, voice preference, and Whisper model persist to the ignored env file."""
    env_path = tmp_path / ".env"

    save_desktop_settings(
        "qwen2.5:3b",
        False,
        "base",
        env_path,
        "alt+space",
        True,
    )

    assert dotenv_values(env_path) == {
        "OLLAMA_MODEL": "qwen2.5:3b",
        "VOICE_ENABLED": "false",
        "WHISPER_MODEL": "base",
        "GLOBAL_HOTKEY": "alt+space",
        "START_WITH_WINDOWS": "true",
    }


@pytest.mark.parametrize(
    ("model_name", "whisper_model", "global_hotkey"),
    [
        ("", "base", "ctrl+space"),
        ("qwen2.5:3b", "", "ctrl+space"),
        ("qwen2.5:3b", "base", ""),
    ],
)
def test_save_desktop_settings_rejects_empty_models(
    tmp_path: Path,
    model_name: str,
    whisper_model: str,
    global_hotkey: str,
) -> None:
    """Invalid settings fail explicitly without writing an env file."""
    env_path = tmp_path / ".env"

    with pytest.raises(ValueError):
        save_desktop_settings(
            model_name,
            True,
            whisper_model,
            env_path,
            global_hotkey,
        )

    assert not env_path.exists()
