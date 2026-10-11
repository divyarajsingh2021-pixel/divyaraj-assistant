"""Tests for push-to-talk speech recognition with mocked devices and models."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import numpy as np
import pytest

from divyaraj.config import Settings
from divyaraj.stt import (
    LowConfidenceTranscriptError,
    MicrophoneUnavailableError,
    SilentRecordingError,
    SpeechToText,
)


class FakeModel:
    """Scriptable mock of a Faster-Whisper model."""

    def __init__(
        self,
        text: str = "hello",
        *,
        avg_logprob: float = -0.2,
        no_speech_prob: float = 0.1,
    ) -> None:
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = no_speech_prob
        self.options: dict[str, object] = {}

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        beam_size: int,
        vad_filter: bool,
    ) -> tuple[list[SimpleNamespace], SimpleNamespace]:
        self.options = {
            "language": language,
            "beam_size": beam_size,
            "vad_filter": vad_filter,
        }
        return (
            [
                SimpleNamespace(
                    text=self.text,
                    avg_logprob=self.avg_logprob,
                    no_speech_prob=self.no_speech_prob,
                )
            ],
            SimpleNamespace(language="hi"),
        )


class FakeAudioStream:
    """Mock stream that invokes the capture callback once."""

    def __init__(self, callback: Callable[..., None]) -> None:
        self.callback = callback

    def __enter__(self) -> FakeAudioStream:
        self.callback(np.array([[0.1], [0.2]], dtype=np.float32), 2, None, None)
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakeAudioBackend:
    """Mock sounddevice backend without hardware access."""

    class PortAudioError(Exception):
        """Mock device error."""

    def InputStream(
        self,
        *,
        samplerate: int,
        channels: int,
        dtype: str,
        callback: Callable[..., None],
    ) -> FakeAudioStream:
        assert samplerate == 16_000
        assert channels == 1
        assert dtype == "float32"
        return FakeAudioStream(callback)


def test_push_to_talk_records_and_auto_detects_language() -> None:
    """Two Enter presses bracket capture and Whisper detects the language."""
    model = FakeModel()
    prompts: list[str] = []

    def press_enter(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    recognizer = SpeechToText(
        Settings(),
        model=model,
        audio_backend=FakeAudioBackend(),
    )
    transcript = recognizer.listen(input_fn=press_enter)

    assert transcript.text == "hello"
    assert transcript.language == "hi"
    assert model.options == {
        "language": None,
        "beam_size": 1,
        "vad_filter": True,
    }
    assert len(prompts) == 2


def test_silent_audio_is_rejected_before_transcription() -> None:
    """Silence reports a clear message without calling Whisper."""
    recognizer = SpeechToText(Settings(), model=FakeModel())

    with pytest.raises(SilentRecordingError, match="didn't hear"):
        recognizer.transcribe_audio(np.zeros(3200, dtype=np.float32))


def test_low_confidence_transcript_is_rejected() -> None:
    """Uncertain recognition tells the user to repeat the request."""
    recognizer = SpeechToText(
        Settings(),
        model=FakeModel(avg_logprob=-1.8),
    )

    with pytest.raises(LowConfidenceTranscriptError, match="repeat"):
        recognizer.transcribe_audio(np.ones(3200, dtype=np.float32) * 0.1)


def test_missing_microphone_is_reported() -> None:
    """PortAudio device errors become actionable microphone errors."""

    class MissingMicrophone(FakeAudioBackend):
        def InputStream(self, **kwargs: object) -> FakeAudioStream:
            raise self.PortAudioError("no device")

    recognizer = SpeechToText(
        Settings(),
        model=FakeModel(),
        audio_backend=MissingMicrophone(),
    )

    with pytest.raises(MicrophoneUnavailableError, match="No microphone"):
        recognizer.listen(started=True, input_fn=lambda prompt: "")
