"""CPU-friendly push-to-talk speech recognition."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from divyaraj.config import Settings, load_settings

SAMPLE_RATE = 16_000
SILENCE_THRESHOLD = 0.005
MIN_AVERAGE_LOG_PROBABILITY = -1.0
MAX_NO_SPEECH_PROBABILITY = 0.6


class VoiceInputError(RuntimeError):
    """Base error for speech input failures."""


class MicrophoneUnavailableError(VoiceInputError):
    """Raised when a microphone cannot be opened or produces no audio."""


class SilentRecordingError(VoiceInputError):
    """Raised when the captured audio is effectively silent."""


class LowConfidenceTranscriptError(VoiceInputError):
    """Raised when speech recognition cannot confidently understand speech."""


class TranscriptionSegment(Protocol):
    """Required Faster-Whisper segment fields."""

    text: str
    avg_logprob: float
    no_speech_prob: float


class Transcriber(Protocol):
    """Minimal interface implemented by Faster-Whisper models."""

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
        beam_size: int,
        vad_filter: bool,
    ) -> tuple[Sequence[TranscriptionSegment], object]:
        """Transcribe a waveform and return segments plus detected language."""

        ...


class AudioStream(Protocol):
    """Context-managed input stream interface used by sounddevice."""

    def __enter__(self) -> AudioStream:
        """Start the microphone stream."""

        ...

    def __exit__(self, *args: object) -> None:
        """Stop the microphone stream."""

        ...


class AudioBackend(Protocol):
    """Minimal sounddevice interface needed for microphone capture."""

    PortAudioError: type[Exception]

    def InputStream(
        self,
        *,
        samplerate: int,
        channels: int,
        dtype: str,
        callback: Callable[..., None],
    ) -> AudioStream:
        """Create a microphone input stream."""

        ...


@dataclass(frozen=True)
class Transcript:
    """Recognized text and Whisper's detected language."""

    text: str
    language: str | None


class SpeechToText:
    """Record push-to-talk audio and transcribe it on the CPU."""

    def __init__(
        self,
        settings: Settings | None = None,
        model: Transcriber | None = None,
        audio_backend: AudioBackend | None = None,
    ) -> None:
        """Configure a lazy-loaded CPU model and optional test backends."""
        self.settings = settings or load_settings()
        self._model = model
        self._audio_backend = audio_backend

    def listen(
        self,
        *,
        started: bool = False,
        input_fn: Callable[[str], str] | None = None,
    ) -> Transcript:
        """Record until Enter, then transcribe with automatic language detection."""
        read_input = input_fn or input
        if not started:
            read_input("Press Enter to start recording...")

        audio = self._capture_until_enter(read_input)
        return self.transcribe_audio(audio)

    def transcribe_audio(self, audio: np.ndarray) -> Transcript:
        """Transcribe audio and reject silent or low-confidence results."""
        if audio.size == 0:
            raise MicrophoneUnavailableError(
                "No audio was captured. Check that a microphone is connected."
            )
        if float(np.max(np.abs(audio))) < SILENCE_THRESHOLD:
            raise SilentRecordingError(
                "I didn't hear anything. Please speak clearly and try again."
            )

        model = self._model or self._load_model()
        self._model = model
        try:
            segments, info = model.transcribe(
                audio,
                language=None,
                beam_size=1,
                vad_filter=True,
            )
            recognized_segments = list(segments)
        except (OSError, RuntimeError, ValueError) as error:
            raise VoiceInputError(
                f"Speech recognition failed: {error}. Try again or use --model tiny."
            ) from error

        text = " ".join(segment.text.strip() for segment in recognized_segments).strip()
        if not text:
            raise LowConfidenceTranscriptError(
                "I couldn't understand that. Please repeat it more clearly."
            )
        average_log_probability = sum(
            segment.avg_logprob for segment in recognized_segments
        ) / len(recognized_segments)
        max_no_speech_probability = max(
            segment.no_speech_prob for segment in recognized_segments
        )
        if (
            average_log_probability < MIN_AVERAGE_LOG_PROBABILITY
            or max_no_speech_probability > MAX_NO_SPEECH_PROBABILITY
        ):
            raise LowConfidenceTranscriptError(
                "I wasn't confident I heard that correctly. Please repeat it."
            )
        language = getattr(info, "language", None)
        return Transcript(text=text, language=language)

    def _capture_until_enter(
        self,
        input_fn: Callable[[str], str],
    ) -> np.ndarray:
        """Capture mono audio while the user speaks, stopping on Enter."""
        audio_backend = self._audio_backend or self._load_audio_backend()
        chunks: list[np.ndarray] = []
        callback_errors: list[str] = []

        def capture(
            indata: np.ndarray, frames: int, time_info: object, status: object
        ) -> None:
            if status:
                callback_errors.append(str(status))
            chunks.append(indata.copy())

        try:
            with audio_backend.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=capture,
            ):
                input_fn("Recording... press Enter to stop.")
        except audio_backend.PortAudioError as error:
            raise MicrophoneUnavailableError(
                "No microphone is available. Connect or enable a microphone and retry."
            ) from error
        except OSError as error:
            raise MicrophoneUnavailableError(
                f"Could not access the microphone: {error}"
            ) from error

        if callback_errors:
            raise MicrophoneUnavailableError(
                f"Microphone recording failed: {callback_errors[0]}"
            )
        if not chunks:
            raise MicrophoneUnavailableError(
                "No audio was captured. Check that a microphone is connected."
            )
        return np.concatenate(chunks, axis=0).reshape(-1)

    def _load_model(self) -> Transcriber:
        """Load Faster-Whisper on CPU using the configured lightweight model."""
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise VoiceInputError(
                "Speech recognition is unavailable. Install dependencies with "
                "'python -m pip install -e \".[dev]\"'."
            ) from error
        try:
            return WhisperModel(
                self.settings.stt_model,
                device="cpu",
                compute_type=self.settings.stt_compute_type,
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise VoiceInputError(
                f"Could not load Whisper model '{self.settings.stt_model}': {error}"
            ) from error

    def _load_audio_backend(self) -> AudioBackend:
        """Load sounddevice or report the missing audio dependency."""
        try:
            import sounddevice
        except ImportError as error:
            raise VoiceInputError(
                "Microphone support is unavailable. Install it with "
                "'python -m pip install sounddevice'."
            ) from error
        return sounddevice
