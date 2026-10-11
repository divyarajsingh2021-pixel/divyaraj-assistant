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
    Transcript,
    is_low_confidence_transcript,
)


class FakeModel:
    """Scriptable mock of a Faster-Whisper model."""

    def __init__(
        self,
        text: str = "hello there",
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

    assert transcript.text == "hello there"
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

    with pytest.raises(
        LowConfidenceTranscriptError,
        match="Sorry, I didn't catch that. Please say it again.",
    ):
        recognizer.transcribe_audio(np.ones(3200, dtype=np.float32) * 0.1)


def test_short_high_confidence_transcript_is_rejected() -> None:
    """A very short transcript does not pass merely because Whisper is confident."""
    recognizer = SpeechToText(Settings(), model=FakeModel(text="hi"))

    with pytest.raises(LowConfidenceTranscriptError, match="Sorry, I didn't catch"):
        recognizer.transcribe_audio(np.ones(3200, dtype=np.float32) * 0.1)


def test_whisper_load_uses_configured_base_model_on_cpu(monkeypatch) -> None:
    """Default model is base, CPU int8, with language detection enabled."""
    import faster_whisper

    loaded: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            loaded["model_name"] = model_name
            loaded.update(kwargs)

    monkeypatch.setattr(faster_whisper, "WhisperModel", FakeWhisperModel)
    recognizer = SpeechToText(Settings())

    recognizer._load_model()

    assert loaded == {
        "model_name": "base",
        "device": "cpu",
        "compute_type": "int8",
        "download_root": str(Settings().whisper_download_dir),
    }


@pytest.mark.parametrize("text", ["hi", "hmm", "aaaaa", "..."])
def test_short_or_noise_transcripts_are_rejected(text: str) -> None:
    """Very short and non-speech-like transcripts do not reach the agent."""
    recognizer = SpeechToText(Settings(), model=FakeModel(text=text))

    with pytest.raises(
        LowConfidenceTranscriptError,
        match="Sorry, I didn't catch that. Please say it again.",
    ):
        recognizer.transcribe_audio(np.ones(3200, dtype=np.float32) * 0.1)


@pytest.mark.parametrize("text", ["hi", "hmm", "noise", "hello there"])
def test_cli_transcript_guard(text: str) -> None:
    """CLI guard rejects short/noise text but accepts a normal utterance."""
    expected = len(text.split()) < 2 or text in {"hmm", "noise"}
    assert (
        is_low_confidence_transcript(Transcript(text=text, language="en")) is expected
    )


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
