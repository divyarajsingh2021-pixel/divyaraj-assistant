"""Tests for command-line model selection and Ollama error messaging."""

import sys
from pathlib import Path

import pytest

from divyaraj import __main__ as cli
from divyaraj.config import Settings
from divyaraj.core.llm import OllamaUnavailableError


def test_cli_passes_model_option_to_ollama(monkeypatch, capsys, tmp_path: Path) -> None:
    """The --model option overrides the configured default."""
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj", "--model", "selected-model"])
    prompts = iter(["hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(prompts))
    clients = []
    agents = []

    class FakeOllamaClient:
        def __init__(self, configuration: Settings) -> None:
            clients.append(configuration)

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            agents.append(kwargs)

        def respond(self, message: str) -> str:
            return "mocked reply"

    monkeypatch.setattr(cli, "OllamaClient", FakeOllamaClient)
    monkeypatch.setattr(cli, "Agent", FakeAgent)

    cli.main()

    assert clients[0].ollama_model == "selected-model"
    assert callable(agents[0]["confirmation_callback"])
    assert "Model: selected-model" in capsys.readouterr().out


def test_cli_explains_how_to_recover_when_ollama_is_offline(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    """An offline-model error suggests starting Ollama and pulling the model."""
    settings = Settings(data_dir=tmp_path, ollama_model="qwen2.5:3b")
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj"])
    prompts = iter(["hello", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(prompts))
    monkeypatch.setattr(cli, "OllamaClient", lambda configuration: object())

    class OfflineAgent:
        def __init__(self, **kwargs: object) -> None:
            pass

        def respond(self, message: str) -> str:
            raise OllamaUnavailableError("Could not reach Ollama.")

    monkeypatch.setattr(cli, "Agent", OfflineAgent)

    cli.main()

    error_output = capsys.readouterr().err
    assert "Could not reach Ollama." in error_output
    assert "ollama pull qwen2.5:3b" in error_output


def test_voice_mode_routes_transcribed_turn_and_mute_commands(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    """Voice mode transcribes turns, prints replies, and honors mute toggles."""
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj", "--voice"])
    prompts = iter(["", "/mute", "", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(prompts))
    speech_to_text_instances = []
    text_to_speech_instances = []
    agent_instances = []

    class FakeSpeechToText:
        def __init__(self, configuration: Settings) -> None:
            self.listen_calls = 0
            speech_to_text_instances.append(self)

        def listen(self, *, started: bool) -> object:
            assert started
            self.listen_calls += 1
            return type("Result", (), {"text": "Tell me a joke."})()

    class FakeTextToSpeech:
        def __init__(self, configuration: Settings) -> None:
            self.calls: list[tuple[str, bool]] = []
            text_to_speech_instances.append(self)

        def speak(self, text: str, *, muted: bool = False) -> None:
            self.calls.append((text, muted))

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            agent_instances.append(self)

        def respond(self, message: str) -> str:
            return "A short reply."

    monkeypatch.setattr(cli, "OllamaClient", lambda configuration: object())
    monkeypatch.setattr(cli, "Agent", FakeAgent)
    monkeypatch.setattr(cli, "SpeechToText", FakeSpeechToText)
    monkeypatch.setattr(cli, "TextToSpeech", FakeTextToSpeech)

    cli.main()

    assert len(speech_to_text_instances) == 1
    assert speech_to_text_instances[0].listen_calls == 2
    assert text_to_speech_instances[0].calls == [
        ("A short reply.", False),
        ("A short reply.", True),
    ]
    output = capsys.readouterr().out
    assert "Model: qwen2.5:3b" in output
    assert "Speech recognition model: base (CPU, int8)" in output


def test_direct_time_command_prints_human_friendly_value(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    """The text-mode shortcut does not print an ISO timestamp."""
    from divyaraj.core.tools.base import Tool

    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj"])
    prompts = iter(["/time", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(prompts))

    class FixedClockTool(Tool):
        name = "get_time"
        description = "Fixed local time for the CLI test."
        args_schema: dict[str, object] = {"type": "object"}

        def run(self, arguments: dict[str, object]) -> str:
            return "2026-10-11T21:47:00+05:30"

    monkeypatch.setattr(cli, "get_tool", lambda name: FixedClockTool())
    monkeypatch.setattr(cli, "OllamaClient", lambda configuration: object())

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            pass

    monkeypatch.setattr(cli, "Agent", FakeAgent)

    cli.main()

    output = capsys.readouterr().out
    assert "It's 9:47 PM on Sunday, 11 October." in output
    assert "2026-10-11T" not in output


def test_low_confidence_voice_transcript_does_not_call_agent(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    """A one-word transcript gets a retry prompt and never reaches the LLM."""
    from divyaraj.stt import Transcript

    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj", "--voice"])
    prompts = iter(["", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(prompts))

    class FakeSpeechToText:
        def __init__(self, configuration: Settings) -> None:
            pass

        def listen(self, *, started: bool) -> Transcript:
            return Transcript(text="hi", language="en")

    class NeverCalledAgent:
        def __init__(self, **kwargs: object) -> None:
            pass

        def respond(self, message: str) -> str:
            pytest.fail("Low-confidence input must not reach the agent.")

    class FakeTextToSpeech:
        def __init__(self, configuration: Settings) -> None:
            pass

    monkeypatch.setattr(cli, "OllamaClient", lambda configuration: object())
    monkeypatch.setattr(cli, "Agent", NeverCalledAgent)
    monkeypatch.setattr(cli, "SpeechToText", FakeSpeechToText)
    monkeypatch.setattr(cli, "TextToSpeech", FakeTextToSpeech)

    cli.main()

    assert "Sorry, I didn't catch that. Please say it again." in capsys.readouterr().out


def test_gui_flag_starts_desktop_without_entering_cli(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The --gui option dispatches directly to the desktop application."""
    import types

    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["divyaraj", "--gui"])
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "divyaraj.ui_desktop.app",
        types.SimpleNamespace(run_desktop=calls.append),
    )

    cli.main()

    assert calls == [settings]
