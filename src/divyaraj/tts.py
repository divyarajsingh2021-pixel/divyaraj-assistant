"""Offline speech synthesis with Piper and a pyttsx3 fallback."""

import io
import logging
import re
import wave
from pathlib import Path
from typing import Protocol

import numpy as np

from divyaraj.config import Settings, load_settings
from divyaraj.core.replies import format_tool_reply

LOGGER = logging.getLogger(__name__)


class AudioOutput(Protocol):
    """Minimal sounddevice playback interface."""

    PortAudioError: type[Exception]

    def play(self, audio: np.ndarray, samplerate: int) -> None:
        """Play a mono waveform."""

        ...

    def wait(self) -> None:
        """Wait for playback to finish."""

        ...


class PiperVoice(Protocol):
    """Minimal Piper voice interface."""

    def synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        """Write synthesized speech into a WAV stream."""

        ...


class SpeechEngine(Protocol):
    """Minimal pyttsx3 engine interface."""

    def say(self, text: str) -> None:
        """Queue text for system speech."""

        ...

    def runAndWait(self) -> None:
        """Play queued speech and wait for it to finish."""

        ...


class SpeechOutputError(RuntimeError):
    """Raised when neither offline speech engine can produce speech."""


def format_for_speech(text: str) -> str:
    """Format machine-readable local timestamps naturally for spoken replies."""
    return format_tool_reply("get_time", text).strip()


def shorten_for_speech(text: str, max_characters: int = 240) -> str:
    """Keep spoken replies concise while leaving full text visible in chat."""
    formatted = format_for_speech(text)
    if len(formatted) <= max_characters:
        return formatted
    sentences = re.split(r"(?<=[.!?])\s+", formatted)
    concise = " ".join(sentences[:2]).strip()
    if len(concise) <= max_characters:
        return concise
    clipped = formatted[: max(1, max_characters - 1)].rsplit(" ", 1)[0].rstrip()
    return f"{clipped}…" if clipped else formatted[:max_characters]


class TextToSpeech:
    """Speak concise replies offline, preferring a configured Piper voice."""

    def __init__(
        self,
        settings: Settings | None = None,
        piper_voice: PiperVoice | None = None,
        audio_output: AudioOutput | None = None,
        speech_engine: SpeechEngine | None = None,
    ) -> None:
        """Configure offline speech engines and optional mockable backends."""
        self.settings = settings or load_settings()
        self._piper_voice = piper_voice
        self._audio_output = audio_output
        self._speech_engine = speech_engine
        self._piper_checked = piper_voice is not None

    def speak(self, text: str, *, muted: bool = False) -> None:
        """Speak a shortened reply unless voice output is muted."""
        if muted:
            return
        speech_text = shorten_for_speech(
            text,
            max_characters=self.settings.speech_max_characters,
        )
        if not speech_text:
            return

        if self._load_piper_voice():
            try:
                self._speak_with_piper(speech_text)
                return
            except (OSError, RuntimeError, ValueError) as error:
                LOGGER.warning("Piper speech failed (%s); switching to pyttsx3.", error)
                self._piper_voice = None

        LOGGER.warning(
            "Piper voice unavailable. Install Piper with "
            "'python -m pip install piper-tts', download a voice model and its "
            "JSON config, then set PIPER_MODEL_PATH. Using pyttsx3 fallback."
        )
        self._speak_with_pyttsx3(speech_text)

    def _load_piper_voice(self) -> PiperVoice | None:
        """Load Piper lazily when both its package and model are available."""
        if self._piper_checked:
            return self._piper_voice
        self._piper_checked = True
        model_path = self.settings.piper_model_path
        config_path = Path(f"{model_path}.json")
        if not model_path.is_file() or not config_path.is_file():
            LOGGER.warning(
                "Piper model is missing at '%s' or its JSON config is absent.",
                model_path,
            )
            return None
        try:
            from piper import PiperVoice as PiperVoiceLoader
        except ImportError:
            return None
        try:
            self._piper_voice = PiperVoiceLoader.load(str(model_path))
        except (OSError, RuntimeError, ValueError) as error:
            LOGGER.warning("Could not load Piper voice model: %s", error)
            return None
        return self._piper_voice

    def _speak_with_piper(self, text: str) -> None:
        """Synthesize Piper output in memory and play it through sounddevice."""
        voice = self._piper_voice
        if voice is None:
            raise RuntimeError("Piper voice is not loaded.")
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        wav_buffer.seek(0)
        with wave.open(wav_buffer, "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            frames = wav_file.readframes(wav_file.getnframes())
        if sample_width != 2:
            raise SpeechOutputError(
                f"Unsupported Piper sample width: {sample_width} bytes."
            )
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        audio_output = self._load_audio_output()
        try:
            audio_output.play(audio, samplerate=sample_rate)
            audio_output.wait()
        except audio_output.PortAudioError as error:
            raise SpeechOutputError(
                "Could not play Piper speech. Check your speakers or audio output "
                "device."
            ) from error

    def _speak_with_pyttsx3(self, text: str) -> None:
        """Use the system's installed offline speech engine as a fallback."""
        engine = self._speech_engine or self._load_speech_engine()
        try:
            engine.say(text)
            engine.runAndWait()
        except (OSError, RuntimeError) as error:
            raise SpeechOutputError(
                "Offline speech output failed. Install pyttsx3 with "
                "'python -m pip install pyttsx3' and check Windows speech voices."
            ) from error

    def _load_audio_output(self) -> AudioOutput:
        """Load sounddevice playback or report how to install it."""
        if self._audio_output is not None:
            return self._audio_output
        try:
            import sounddevice
        except ImportError as error:
            raise SpeechOutputError(
                "Piper playback requires sounddevice. Install it with "
                "'python -m pip install sounddevice'."
            ) from error
        self._audio_output = sounddevice
        return self._audio_output

    def _load_speech_engine(self) -> SpeechEngine:
        """Initialize pyttsx3 or raise an actionable offline-speech error."""
        try:
            import pyttsx3
        except ImportError as error:
            raise SpeechOutputError(
                "No speech engine is installed. Install pyttsx3 with "
                "'python -m pip install pyttsx3'."
            ) from error
        try:
            self._speech_engine = pyttsx3.init()
        except (ImportError, OSError, RuntimeError) as error:
            raise SpeechOutputError(
                "Could not initialize pyttsx3. Install it with "
                "'python -m pip install pyttsx3' and check Windows speech voices."
            ) from error
        return self._speech_engine
