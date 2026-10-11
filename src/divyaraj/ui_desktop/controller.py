"""Threaded coordination between the desktop window and assistant services."""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass, field
from threading import Event, Thread
from typing import Literal, Protocol

from divyaraj.core.llm import OllamaUnavailableError
from divyaraj.core.tools.base import Tool
from divyaraj.stt import SpeechToText, VoiceInputError, is_low_confidence_transcript
from divyaraj.tts import SpeechOutputError, TextToSpeech

LOGGER = logging.getLogger(__name__)


class Assistant(Protocol):
    """Agent interface required by the desktop worker."""

    def respond(self, message: str) -> str:
        """Process one user message and return the assistant reply."""


EventKind = Literal[
    "status",
    "transcript",
    "reply",
    "error",
    "offline",
    "confirmation",
]
JobKind = Literal["text", "voice"]


@dataclass(frozen=True)
class DesktopJob:
    """One user turn submitted to the background worker."""

    kind: JobKind
    message: str = ""
    speak: bool = False
    stop_event: Event | None = None


@dataclass(frozen=True)
class DesktopEvent:
    """A worker-to-window update consumed only by the UI thread."""

    kind: EventKind
    text: str = ""
    confirmation: ConfirmationRequest | None = None
    retry_job: DesktopJob | None = None


@dataclass
class ConfirmationRequest:
    """A risky-tool confirmation waiting for a decision in the window."""

    tool: Tool
    _decision: Event = field(default_factory=Event)
    _approved: bool = False

    def resolve(self, approved: bool) -> None:
        """Wake the waiting tool call with the user's Yes/No decision."""
        self._approved = approved
        self._decision.set()

    def wait(self) -> bool:
        """Wait for the UI to decide whether the risky action may run."""
        self._decision.wait()
        return self._approved


class ConfirmationBroker:
    """Bridge synchronous safety callbacks to asynchronous UI dialogs."""

    def __init__(self, events: queue.Queue[DesktopEvent]) -> None:
        """Create a broker publishing prompts to the supplied UI event queue."""
        self._events = events

    def confirm(self, tool: Tool) -> bool:
        """Request a UI decision and block only the assistant worker."""
        request = ConfirmationRequest(tool)
        self._events.put(DesktopEvent(kind="confirmation", confirmation=request))
        return request.wait()


class DesktopController:
    """Run agent, speech recognition, and speech output off the UI thread."""

    def __init__(
        self,
        agent: Assistant,
        speech_to_text: SpeechToText,
        text_to_speech: TextToSpeech,
        events: queue.Queue[DesktopEvent] | None = None,
    ) -> None:
        """Start a daemon worker using the existing assistant and voice services."""
        self.events = events or queue.Queue()
        self._agent = agent
        self._speech_to_text = speech_to_text
        self._text_to_speech = text_to_speech
        self._jobs: queue.Queue[DesktopJob | None] = queue.Queue()
        self._recording_stop: Event | None = None
        self._thread = Thread(target=self._run, name="divyaraj-desktop", daemon=True)
        self._thread.start()

    def submit_text(self, message: str, *, speak: bool) -> None:
        """Queue a text turn for background processing."""
        self._jobs.put(DesktopJob(kind="text", message=message, speak=speak))

    def start_voice(self, *, speak: bool) -> None:
        """Queue a push-to-talk turn and retain its stop signal."""
        if self._recording_stop is not None:
            return
        stop_event = Event()
        self._recording_stop = stop_event
        self._jobs.put(DesktopJob(kind="voice", speak=speak, stop_event=stop_event))

    def stop_voice(self) -> None:
        """Stop the current recording when the user clicks the mic again."""
        if self._recording_stop is not None:
            self._recording_stop.set()

    def resolve_confirmation(
        self,
        request: ConfirmationRequest,
        approved: bool,
    ) -> None:
        """Deliver a UI confirmation decision to the waiting worker."""
        request.resolve(approved)

    def retry(self, job: DesktopJob) -> None:
        """Retry a turn that failed because Ollama was unavailable."""
        self._jobs.put(job)

    def close(self) -> None:
        """Signal an active recording and allow the daemon worker to exit."""
        self.stop_voice()
        self._jobs.put(None)

    def _run(self) -> None:
        """Consume queued turns until the window requests shutdown."""
        while True:
            job = self._jobs.get()
            if job is None:
                return
            try:
                self._process(job)
            except (SpeechOutputError, VoiceInputError, ValueError) as error:
                self.events.put(DesktopEvent(kind="error", text=str(error)))
            except Exception as error:
                LOGGER.exception("Unexpected desktop worker failure")
                self.events.put(
                    DesktopEvent(
                        kind="error",
                        text=f"Something went wrong: {error}",
                    )
                )
            finally:
                if job.stop_event is not None:
                    self._recording_stop = None
                self.events.put(DesktopEvent(kind="status", text="Idle"))

    def _process(self, job: DesktopJob) -> None:
        """Run one text or voice turn and optionally speak the result."""
        message = job.message
        if job.kind == "voice":
            self.events.put(DesktopEvent(kind="status", text="Listening"))
            stop_event = job.stop_event
            if stop_event is None:
                raise ValueError("Voice job is missing its recording stop signal.")

            def wait_until_stopped(prompt: str) -> str:
                LOGGER.debug("%s", prompt)
                stop_event.wait()
                return ""

            transcript = self._speech_to_text.listen(
                started=True,
                input_fn=wait_until_stopped,
            )
            message = transcript.text.strip()
            if is_low_confidence_transcript(transcript):
                raise VoiceInputError(
                    "Sorry, I didn't catch that. Please say it again."
                )
            self.events.put(DesktopEvent(kind="transcript", text=message))

        if not message.strip():
            raise ValueError("Message must not be empty.")
        self.events.put(DesktopEvent(kind="status", text="Thinking"))
        try:
            reply = self._agent.respond(message)
        except OllamaUnavailableError as error:
            retry_job = DesktopJob(kind="text", message=message, speak=job.speak)
            self.events.put(
                DesktopEvent(
                    kind="offline",
                    text=str(error),
                    retry_job=retry_job,
                )
            )
            return
        self.events.put(DesktopEvent(kind="reply", text=reply))
        if job.speak:
            self.events.put(DesktopEvent(kind="status", text="Speaking"))
            self._text_to_speech.speak(reply)
