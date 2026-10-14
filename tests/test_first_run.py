"""Tests for first-run preparation without network or model downloads."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from divyaraj.config import Settings
from divyaraj.first_run import (
    OLLAMA_DOWNLOAD_URL,
    SetupError,
    _check_ollama,
    _ensure_ollama_model,
    _ensure_piper_voice,
    prepare_first_run,
)


class FakeResponse:
    """Minimal successful HTTP response used for mocked setup requests."""

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


def test_prepare_first_run_runs_each_setup_stage(monkeypatch, tmp_path: Path) -> None:
    """First-run orchestration reports each dependency stage and completion."""
    import divyaraj.first_run as first_run

    settings = Settings(
        data_dir=tmp_path,
        piper_model_path=tmp_path / "models" / "en_US-lessac-medium.onnx",
    )
    calls: list[str] = []
    monkeypatch.setattr(
        first_run, "_check_ollama", lambda _settings: calls.append("ollama")
    )
    monkeypatch.setattr(
        first_run,
        "_ensure_ollama_model",
        lambda _settings, _progress, _cancel: calls.append("model"),
    )
    monkeypatch.setattr(
        first_run,
        "_ensure_whisper_model",
        lambda _settings, _progress: calls.append("whisper"),
    )
    monkeypatch.setattr(
        first_run,
        "_ensure_piper_voice",
        lambda _settings, _progress, _cancel: calls.append("piper"),
    )
    updates: list[tuple[str, str, float | None]] = []

    prepare_first_run(settings, lambda *update: updates.append(update))

    assert calls == ["ollama", "model", "whisper", "piper"]
    assert updates[-1] == ("complete", "Setup complete.", 100)


def test_check_ollama_gives_download_guidance_when_not_installed(monkeypatch) -> None:
    """Missing Ollama reports the official download page."""
    import divyaraj.first_run as first_run

    monkeypatch.setattr(first_run, "_find_ollama_executable", lambda: None)

    with pytest.raises(SetupError, match=OLLAMA_DOWNLOAD_URL):
        _check_ollama(Settings())


def test_check_ollama_reports_unavailable_service(monkeypatch) -> None:
    """An installed executable with a stopped service produces a retry hint."""
    import divyaraj.first_run as first_run

    monkeypatch.setattr(first_run, "_find_ollama_executable", lambda: "ollama.exe")
    monkeypatch.setattr(
        first_run.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    with pytest.raises(SetupError, match="Start Ollama"):
        _check_ollama(Settings())


def test_ensure_ollama_model_pulls_and_reports_progress(monkeypatch) -> None:
    """An absent model is pulled and streamed progress reaches the UI callback."""
    import divyaraj.first_run as first_run

    monkeypatch.setattr(
        first_run.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse({"models": []}),
    )
    updates: list[tuple[str, str, float | None]] = []

    class FakeClient:
        def __init__(self, host: str) -> None:
            assert host == "http://localhost:11434"

        def pull(self, model: str, *, stream: bool) -> list[dict[str, object]]:
            assert model == "qwen2.5:1.5b"
            assert stream
            return [
                {"status": "downloading", "completed": 25, "total": 100},
                {"status": "success", "completed": 100, "total": 100},
            ]

    monkeypatch.setitem(
        sys.modules,
        "ollama",
        SimpleNamespace(Client=FakeClient, ResponseError=Exception),
    )
    _ensure_ollama_model(Settings(), lambda *update: updates.append(update), None)

    assert updates == [
        ("ollama", "Downloading Ollama model qwen2.5:1.5b…", 0),
        ("ollama", "downloading", 25),
        ("ollama", "success", 100),
    ]


def test_ensure_ollama_model_handles_none_progress_values(monkeypatch) -> None:
    """Ollama progress updates with None completed/total are handled gracefully."""
    import divyaraj.first_run as first_run

    monkeypatch.setattr(
        first_run.httpx,
        "get",
        lambda *args, **kwargs: FakeResponse({"models": []}),
    )
    updates: list[tuple[str, str, float | None]] = []

    class FakeClient:
        def __init__(self, host: str) -> None:
            pass

        def pull(self, model: str, *, stream: bool) -> list[dict[str, object]]:
            return [
                {"status": "pulling manifest", "completed": None, "total": 1000},
                {"status": "verifying sha256", "completed": 500, "total": None},
                {"status": "writing manifest", "completed": None, "total": None},
                {"status": "success", "completed": 1000, "total": 1000},
            ]

    monkeypatch.setitem(
        sys.modules,
        "ollama",
        SimpleNamespace(Client=FakeClient, ResponseError=Exception),
    )
    _ensure_ollama_model(Settings(), lambda *update: updates.append(update), None)

    assert updates == [
        ("ollama", "Downloading Ollama model qwen2.5:1.5b…", 0),
        ("ollama", "pulling manifest", 0.0),
        ("ollama", "verifying sha256", None),
        ("ollama", "writing manifest", None),
        ("ollama", "success", 100.0),
    ]


def test_piper_download_writes_user_data_model_and_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Both free Piper assets download atomically into the configured user folder."""
    import divyaraj.first_run as first_run

    requests: list[str] = []

    class FakeStreamResponse:
        headers = {"content-length": "8"}

        def __init__(self, url: str) -> None:
            self.url = url

        def __enter__(self) -> FakeStreamResponse:
            requests.append(self.url)
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self, chunk_size: int) -> list[bytes]:
            assert chunk_size == 1024 * 256
            return [b"voice-", b"data!"]

    monkeypatch.setattr(
        first_run.httpx,
        "stream",
        lambda method, url, **kwargs: FakeStreamResponse(url),
    )
    settings = Settings(
        data_dir=tmp_path,
        piper_model_path=tmp_path / "models" / "en_US-lessac-medium.onnx",
    )
    updates: list[tuple[str, str, float | None]] = []

    _ensure_piper_voice(settings, lambda *update: updates.append(update), None)

    assert len(requests) == 2
    assert settings.piper_model_path.read_bytes() == b"voice-data!"
    assert Path(f"{settings.piper_model_path}.json").read_bytes() == b"voice-data!"
    assert not list(tmp_path.rglob("*.part"))
    assert all(update[0] == "piper" for update in updates)


def test_piper_download_network_error_is_actionable(
    monkeypatch, tmp_path: Path
) -> None:
    """Download failures are converted to explicit retry guidance."""
    import divyaraj.first_run as first_run

    def failed_stream(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr(first_run.httpx, "stream", failed_stream)
    settings = Settings(
        data_dir=tmp_path,
        piper_model_path=tmp_path / "models" / "en_US-lessac-medium.onnx",
    )

    with pytest.raises(SetupError, match="Check your internet connection"):
        _ensure_piper_voice(settings, lambda *args: None, None)

    assert not list(tmp_path.rglob("*.part"))


def test_cached_whisper_model_is_not_downloaded_again(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A complete cached Whisper model avoids repeat downloads."""
    import divyaraj.first_run as first_run

    settings = Settings(data_dir=tmp_path)
    cached_snapshot = (
        settings.whisper_download_dir
        / "models--Systran--faster-whisper-base"
        / "snapshots"
        / "revision"
    )
    cached_snapshot.mkdir(parents=True)
    for filename in ("config.json", "model.bin", "tokenizer.json"):
        (cached_snapshot / filename).touch()
    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = lambda **kwargs: pytest.fail("model redownload")
    errors = ModuleType("huggingface_hub.errors")
    errors.HfHubHTTPError = RuntimeError
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", errors)
    updates: list[tuple[str, str, float | None]] = []

    first_run._ensure_whisper_model(settings, lambda *update: updates.append(update))

    assert updates == [("whisper", "Whisper model base is ready.", 100)]


def test_whisper_download_uses_per_user_cache(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Whisper weights are fetched into user data without loading CPU inference."""
    import divyaraj.first_run as first_run

    settings = Settings(data_dir=tmp_path)
    received: dict[str, object] = {}

    def snapshot_download(**kwargs: object) -> str:
        received.update(kwargs)
        return str(tmp_path / "snapshot")

    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = snapshot_download
    errors = ModuleType("huggingface_hub.errors")
    errors.HfHubHTTPError = RuntimeError
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", errors)
    updates: list[tuple[str, str, float | None]] = []

    first_run._ensure_whisper_model(settings, lambda *update: updates.append(update))

    assert received["repo_id"] == "Systran/faster-whisper-base"
    assert received["cache_dir"] == str(settings.whisper_download_dir)
    assert "model.bin" in received["allow_patterns"]
    assert updates[0][0] == "whisper"


def test_whisper_network_failure_is_actionable(monkeypatch, tmp_path: Path) -> None:
    """Hugging Face network failures provide clear connection guidance."""
    import divyaraj.first_run as first_run

    hub = ModuleType("huggingface_hub")

    def failed_download(**kwargs: object) -> str:
        raise RuntimeError("network unavailable")

    hub.snapshot_download = failed_download
    errors = ModuleType("huggingface_hub.errors")
    errors.HfHubHTTPError = RuntimeError
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.errors", errors)
    settings = Settings(data_dir=tmp_path)

    with pytest.raises(SetupError, match="Check your internet connection"):
        first_run._ensure_whisper_model(settings, lambda *args: None)
