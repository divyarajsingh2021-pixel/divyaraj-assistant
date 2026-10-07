"""Tests for command-line model selection and Ollama error messaging."""

import sys
from pathlib import Path

from divyaraj import __main__ as cli
from divyaraj.config import Settings
from divyaraj.core.llm import OllamaUnavailableError


def test_cli_passes_model_option_to_ollama(monkeypatch, tmp_path: Path) -> None:
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
