"""Tests for offline speech formatting and synthesis."""

import wave
from pathlib import Path

import numpy as np

from divyaraj.config import Settings
from divyaraj.tts import TextToSpeech, format_for_speech, shorten_for_speech


class FakePiperVoice:
    """Mock Piper voice that writes a small silent WAV."""

    def __init__(self) -> None:
        self.text: str | None = None

    def synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        self.text = text
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22_050)
        wav_file.writeframes(np.zeros(128, dtype=np.int16).tobytes())


class FakeAudioOutput:
    """Mock sounddevice output."""

    class PortAudioError(Exception):
        """Mock audio output device error."""

    def __init__(self) -> None:
        self.played: tuple[np.ndarray, int] | None = None
        self.waited = False

    def play(self, audio: np.ndarray, samplerate: int) -> None:
        self.played = audio, samplerate

    def wait(self) -> None:
        self.waited = True


class FakeSpeechEngine:
    """Mock pyttsx3 fallback engine."""

    def __init__(self) -> None:
        self.spoken: list[str] = []

    def say(self, text: str) -> None:
        self.spoken.append(text)

    def runAndWait(self) -> None:
        return None


def test_time_is_formatted_only_for_spoken_reply() -> None:
    """ISO tool output remains intact while the speech formatter localizes it."""
    raw_time = "2026-10-11T21:18:00+05:30"

    assert format_for_speech(raw_time) == ("It's 9:18 PM on Sunday, 11 October")
    assert format_for_speech("A normal assistant reply.") == (
        "A normal assistant reply."
    )
    assert format_for_speech("2026-10-11") == "2026-10-11"


def test_long_reply_is_shortened_for_speech() -> None:
    """Speech text is capped while the caller keeps its original answer."""
    long_reply = "This is the first sentence. " + ("More details follow. " * 20)

    spoken = shorten_for_speech(long_reply, max_characters=80)

    assert len(spoken) <= 80
    assert spoken.startswith("This is the first sentence.")


def test_piper_voice_synthesizes_and_plays_with_mock_output() -> None:
    """Piper synthesis output is sent to the mocked audio device."""
    voice = FakePiperVoice()
    audio_output = FakeAudioOutput()
    tts = TextToSpeech(
        settings=Settings(speech_max_characters=240),
        piper_voice=voice,
        audio_output=audio_output,
    )

    tts.speak("Hello there.")

    assert voice.text == "Hello there."
    assert audio_output.played is not None
    assert audio_output.played[1] == 22_050
    assert audio_output.waited


def test_missing_piper_uses_pyttsx3_fallback(caplog, tmp_path: Path) -> None:
    """Missing model uses the injected offline fallback and shows install guidance."""
    model_path = tmp_path / "missing.onnx"
    engine = FakeSpeechEngine()
    tts = TextToSpeech(
        settings=Settings(piper_model_path=model_path),
        speech_engine=engine,
    )

    tts.speak("Hello from fallback.")

    assert engine.spoken == ["Hello from fallback."]
    assert "python -m pip install piper-tts" in caplog.text
    assert "PIPER_MODEL_PATH" in caplog.text


def test_piper_playback_failure_uses_pyttsx3_fallback(caplog) -> None:
    """An unavailable audio output falls back to the local speech engine."""
    voice = FakePiperVoice()
    engine = FakeSpeechEngine()

    class MissingAudioOutput(FakeAudioOutput):
        def play(self, audio: np.ndarray, samplerate: int) -> None:
            raise self.PortAudioError("no output device")

    tts = TextToSpeech(
        piper_voice=voice,
        audio_output=MissingAudioOutput(),
        speech_engine=engine,
    )

    tts.speak("Hello from the fallback.")

    assert engine.spoken == ["Hello from the fallback."]
    assert "switching to pyttsx3" in caplog.text


def test_muted_replies_do_not_load_or_speak() -> None:
    """Muted output does not invoke either synthesis backend."""
    engine = FakeSpeechEngine()
    tts = TextToSpeech(speech_engine=engine)

    tts.speak("Do not say this.", muted=True)

    assert engine.spoken == []
