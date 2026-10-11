"""Tests for the non-UI desktop worker and confirmation bridge."""

import queue
from collections.abc import Callable
from threading import Thread

import pytest

from divyaraj.core.tools.base import Tool
from divyaraj.stt import Transcript
from divyaraj.ui_desktop.controller import (
    ConfirmationBroker,
    DesktopController,
    DesktopEvent,
)


class ExampleRiskyTool(Tool):
    """Tool fixture for confirmation handoff tests."""

    name = "open_app"
    description = "Open an allowlisted app."
    args_schema: dict[str, object] = {"type": "object"}
    risky = True

    def run(self, arguments: dict[str, object]) -> str:
        return "opened"


class FakeAgent:
    """Agent fixture that records messages and can simulate Ollama failure."""

    def __init__(self, reply: str = "Hello.", fail_first: bool = False) -> None:
        self.messages: list[str] = []
        self.reply = reply
        self.fail_first = fail_first

    def respond(self, message: str) -> str:
        from divyaraj.core.llm import OllamaUnavailableError

        self.messages.append(message)
        if self.fail_first:
            self.fail_first = False
            raise OllamaUnavailableError("Ollama is unavailable.")
        return self.reply


class FakeSpeechToText:
    """Speech recognizer fixture returning a deterministic transcript."""

    def listen(
        self,
        *,
        started: bool,
        input_fn: Callable[[str], object],
    ) -> Transcript:
        assert started
        input_fn("stop recording")
        return Transcript(text="tell me the time", language="en")


class FakeTextToSpeech:
    """Speech output fixture recording its calls."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


def _read_until(
    events: queue.Queue[DesktopEvent],
    kind: str,
) -> DesktopEvent:
    """Read queued events until the requested event is observed."""
    while True:
        event = events.get(timeout=2)
        if event.kind == kind:
            return event


@pytest.mark.parametrize("approved", [True, False])
def test_confirmation_broker_delivers_yes_and_no_decisions(
    approved: bool,
) -> None:
    """A tool callback waits for the window decision without blocking its thread."""
    events: queue.Queue[DesktopEvent] = queue.Queue()
    broker = ConfirmationBroker(events)
    answers: list[bool] = []

    thread = Thread(
        target=lambda: answers.append(broker.confirm(ExampleRiskyTool())),
        daemon=True,
    )
    thread.start()
    request_event = events.get(timeout=2)

    assert request_event.kind == "confirmation"
    assert request_event.confirmation is not None
    assert request_event.confirmation.tool.name == "open_app"
    request_event.confirmation.resolve(approved)
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert answers == [approved]


def test_text_turn_runs_in_worker_and_speaks_when_enabled() -> None:
    """The controller runs agent/TTS calls off-thread and publishes replies."""
    events: queue.Queue[DesktopEvent] = queue.Queue()
    agent = FakeAgent()
    speech = FakeTextToSpeech()
    controller = DesktopController(agent, FakeSpeechToText(), speech, events)
    controller.submit_text("hello", speak=True)

    assert _read_until(events, "reply").text == "Hello."
    _read_until(events, "status")
    assert agent.messages == ["hello"]
    assert speech.spoken == ["Hello."]
    controller.close()


def test_offline_turn_can_be_retried_without_losing_message() -> None:
    """The retry event retains the original prompt for after Ollama starts."""
    events: queue.Queue[DesktopEvent] = queue.Queue()
    agent = FakeAgent(fail_first=True)
    controller = DesktopController(
        agent, FakeSpeechToText(), FakeTextToSpeech(), events
    )
    controller.submit_text("hello again", speak=False)

    offline = _read_until(events, "offline")
    assert offline.retry_job is not None
    assert offline.retry_job.message == "hello again"
    controller.retry(offline.retry_job)
    assert _read_until(events, "reply").text == "Hello."
    assert agent.messages == ["hello again", "hello again"]
    controller.close()


def test_voice_turn_waits_for_stop_signal_and_emits_transcript() -> None:
    """Voice capture uses the worker's stop event and routes recognized text."""
    events: queue.Queue[DesktopEvent] = queue.Queue()
    agent = FakeAgent(reply="It's 10 PM.")
    controller = DesktopController(
        agent, FakeSpeechToText(), FakeTextToSpeech(), events
    )
    controller.start_voice(speak=False)
    controller.stop_voice()

    assert _read_until(events, "transcript").text == "tell me the time"
    assert _read_until(events, "reply").text == "It's 10 PM."
    assert agent.messages == ["tell me the time"]
    controller.close()
