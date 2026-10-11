"""Persistence helpers for desktop-specific preferences."""

from pathlib import Path

from dotenv import set_key


def save_desktop_settings(
    model_name: str,
    voice_enabled: bool,
    whisper_model: str,
    env_path: Path = Path(".env"),
    global_hotkey: str = "ctrl+space",
    start_with_windows: bool = False,
) -> None:
    """Persist desktop preferences in the repository's ignored .env file."""
    values = {
        "OLLAMA_MODEL": model_name.strip(),
        "VOICE_ENABLED": str(voice_enabled).lower(),
        "WHISPER_MODEL": whisper_model.strip(),
        "GLOBAL_HOTKEY": global_hotkey.strip(),
        "START_WITH_WINDOWS": str(start_with_windows).lower(),
    }
    if not values["OLLAMA_MODEL"]:
        raise ValueError("Model name must not be empty.")
    if not values["WHISPER_MODEL"]:
        raise ValueError("Whisper model must not be empty.")
    if not values["GLOBAL_HOTKEY"]:
        raise ValueError("Global hotkey must not be empty.")
    for key, value in values.items():
        set_key(str(env_path), key, value)
