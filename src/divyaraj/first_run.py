"""First-run downloads and local Ollama model preparation."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from threading import Event
from typing import Protocol

import httpx

from divyaraj.config import Settings

LOGGER = logging.getLogger(__name__)
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/windows"
PIPER_MODEL_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
)
PIPER_CONFIG_URL = f"{PIPER_MODEL_URL}.json"


class SetupError(RuntimeError):
    """A recoverable first-run setup failure with user-facing guidance."""


class SetupCancelled(SetupError):
    """Raised when the user quits while first-run setup is active."""


class ProgressCallback(Protocol):
    """Receive a setup stage, message, and optional percentage."""

    def __call__(self, stage: str, message: str, percent: float | None) -> None:
        """Report setup progress."""


def prepare_first_run(
    settings: Settings,
    progress: ProgressCallback,
    cancel_event: Event | None = None,
) -> None:
    """Check Ollama, pull its model, and download local speech models."""
    _raise_if_cancelled(cancel_event)
    _check_ollama(settings)
    _ensure_ollama_model(settings, progress, cancel_event)
    _raise_if_cancelled(cancel_event)
    _ensure_whisper_model(settings, progress)
    _raise_if_cancelled(cancel_event)
    _ensure_piper_voice(settings, progress, cancel_event)
    progress("complete", "Setup complete.", 100)


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    """Stop setup at a stage boundary after a quit request."""
    if cancel_event is not None and cancel_event.is_set():
        raise SetupCancelled("First-run setup was cancelled.")


def _check_ollama(settings: Settings) -> None:
    """Require both a discoverable Ollama executable and responding service."""
    if _find_ollama_executable() is None:
        raise SetupError(
            "Ollama is not installed. Download and install it from "
            f"{OLLAMA_DOWNLOAD_URL}, then choose Retry."
        )
    try:
        response = httpx.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=3,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise SetupError(
            "Ollama is installed but is not responding. Start Ollama, then choose "
            f"Retry. If it is not installed, download it from {OLLAMA_DOWNLOAD_URL}."
        ) from error


def _find_ollama_executable() -> str | None:
    """Locate the Ollama command from PATH or its common Windows install paths."""
    executable = shutil.which("ollama")
    if executable:
        return executable
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        candidates = []
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs/Ollama/ollama.exe")
        program_files = os.environ.get("ProgramFiles")
        if program_files:
            candidates.append(Path(program_files) / "Ollama/ollama.exe")
        return next((str(path) for path in candidates if path.is_file()), None)
    return None


def _ensure_ollama_model(
    settings: Settings,
    progress: ProgressCallback,
    cancel_event: Event | None,
) -> None:
    """Pull the configured model only if it is not already installed."""
    try:
        import ollama
    except ImportError as error:
        raise SetupError(
            "Ollama support is missing from this installation. Reinstall Divyaraj "
            "and retry."
        ) from error
    try:
        response = httpx.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=5,
        )
        response.raise_for_status()
        installed = {
            str(model.get("name", model.get("model", "")))
            for model in response.json().get("models", [])
        }
        if settings.ollama_model in installed:
            progress("ollama", f"Ollama model {settings.ollama_model} is ready.", 100)
            return
        progress("ollama", f"Downloading Ollama model {settings.ollama_model}…", 0)
        client = ollama.Client(host=settings.ollama_base_url)
        for update in client.pull(settings.ollama_model, stream=True):
            _raise_if_cancelled(cancel_event)
            status = _value(update, "status", "Downloading model…")
            total = _value(update, "total", 0)
            completed = _value(update, "completed", 0)
            percent = (completed / total * 100) if total else None
            progress("ollama", str(status), percent)
    except SetupCancelled:
        raise
    except (
        httpx.HTTPError,
        ollama.ResponseError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        raise SetupError(
            f"Could not download Ollama model '{settings.ollama_model}': {error}"
        ) from error


def _value(item: object, name: str, default: object) -> object:
    """Read a response field from either an SDK object or a mapping."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _ensure_whisper_model(
    settings: Settings,
    progress: ProgressCallback,
) -> None:
    """Download the selected Whisper model without loading it into CPU memory."""
    model_path = Path(settings.whisper_model)
    cache_repo = (
        settings.whisper_model
        if "/" in settings.whisper_model
        else f"Systran/faster-whisper-{settings.whisper_model}"
    )
    cache_path = settings.whisper_download_dir / (
        f"models--{cache_repo.replace('/', '--')}"
    )
    if model_path.is_dir() or _cached_whisper_model_exists(cache_path):
        progress("whisper", f"Whisper model {settings.whisper_model} is ready.", 100)
        return
    progress(
        "whisper",
        f"Checking speech recognition model {settings.whisper_model}…",
        None,
    )
    settings.whisper_download_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import HfHubHTTPError

        snapshot_download(
            repo_id=cache_repo,
            cache_dir=str(settings.whisper_download_dir),
            allow_patterns=[
                "config.json",
                "preprocessor_config.json",
                "model.bin",
                "tokenizer.json",
                "vocabulary.*",
            ],
        )
    except ImportError as error:
        raise SetupError(
            "Speech recognition files are missing. Reinstall Divyaraj and retry."
        ) from error
    except (HfHubHTTPError, OSError, RuntimeError, ValueError) as error:
        raise SetupError(
            f"Could not download Whisper model '{settings.whisper_model}'. "
            f"Check your internet connection and retry: {error}"
        ) from error


def _cached_whisper_model_exists(cache_path: Path) -> bool:
    """Check the core model files, not just a partially downloaded weight file."""
    required_files = ("config.json", "model.bin", "tokenizer.json")
    return any(
        all((snapshot / filename).is_file() for filename in required_files)
        for snapshot in cache_path.glob("snapshots/*")
    )


def _ensure_piper_voice(
    settings: Settings,
    progress: ProgressCallback,
    cancel_event: Event | None,
) -> None:
    """Download the default Piper model and config to the user's data directory."""
    model_path = settings.piper_model_path
    config_path = Path(f"{model_path}.json")
    if model_path.is_file() and config_path.is_file():
        progress("piper", "Piper voice is ready.", 100)
        return
    model_path.parent.mkdir(parents=True, exist_ok=True)
    progress("piper", "Downloading the offline Piper voice…", 0)
    _download_file(
        PIPER_MODEL_URL,
        model_path,
        progress,
        "Piper voice model",
        cancel_event,
    )
    try:
        _download_file(
            PIPER_CONFIG_URL,
            config_path,
            progress,
            "Piper voice configuration",
            cancel_event,
        )
    except SetupError:
        model_path.unlink(missing_ok=True)
        raise


def _download_file(
    url: str,
    destination: Path,
    progress: ProgressCallback,
    label: str,
    cancel_event: Event | None,
) -> None:
    """Stream an HTTPS asset to a temporary file and atomically install it."""
    temporary_path = destination.with_suffix(f"{destination.suffix}.part")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            completed = 0
            with temporary_path.open("wb") as model_file:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    _raise_if_cancelled(cancel_event)
                    if not chunk:
                        continue
                    model_file.write(chunk)
                    completed += len(chunk)
                    percent = completed / total * 100 if total else None
                    progress("piper", f"{label} ({completed // 1_048_576} MB)", percent)
        if temporary_path.stat().st_size == 0:
            raise OSError("The downloaded file was empty.")
        temporary_path.replace(destination)
    except (httpx.HTTPError, OSError, ValueError) as error:
        temporary_path.unlink(missing_ok=True)
        raise SetupError(
            f"Could not download {label}. Check your internet connection and retry: "
            f"{error}"
        ) from error
    except SetupCancelled:
        temporary_path.unlink(missing_ok=True)
        raise
