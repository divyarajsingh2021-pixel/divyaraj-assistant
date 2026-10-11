# Divyaraj Assistant

A voice-first personal AI assistant that understands requests, uses tools, and replies naturally.

## Planned features

- Local model support through Ollama, with a provider interface for future alternatives.
- Hindi, English, and Hinglish conversation.
- Speech-to-text and text-to-speech.
- A safety-aware tool system with explicit confirmation for risky actions.
- Conversation memory and a text-only mode.
- Windows desktop app and Android-installable PWA client.

**Status: in development**

## Setup

1. Install [Ollama](https://ollama.com/download) for Windows and start it.
2. Pull the default model:

   ```powershell
   ollama pull qwen2.5:3b
   ```

3. Create a Python 3.11 virtual environment and install the project and its
   development and voice dependencies:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```

4. For offline speech output, download a free Piper voice model and its matching
   `.onnx.json` configuration file from the
   [Piper voices collection](https://github.com/rhasspy/piper-voices) and place both
   files in `models/`. The default path is
   `models/en_US-lessac-medium.onnx`; set `PIPER_MODEL_PATH` if you choose another
   voice. Without Piper or its model, the app uses Windows voices through `pyttsx3`
   and prints setup guidance.
5. Optionally copy `.env.example` to `.env` and set `OLLAMA_MODEL`,
   `OLLAMA_BASE_URL`, `DATA_DIR`, `ALLOWED_APPS`, `STT_MODEL`, `STT_COMPUTE_TYPE`,
   or `PIPER_MODEL_PATH`. `ALLOWED_APPS` is a JSON object mapping approved app names
   to executable paths. `STT_MODEL` defaults to the CPU-light `tiny`; `base` is
   available for improved accuracy if memory allows. STT uses CPU `int8` inference
   and automatically detects Hindi, English, and Hinglish speech.
6. Run the text CLI:

   ```powershell
   python -m divyaraj
   ```

   Use `python -m divyaraj --model qwen2.5:3b` to select a model for one run.
   Type `exit` to quit. Risky tool calls ask for confirmation before execution.
7. Run the voice CLI:

   ```powershell
   python -m divyaraj --voice
   ```

   Press Enter to begin push-to-talk, then press Enter again to stop recording.
   Type `/mute` between turns to turn spoken responses off and `/unmute` to turn
   them back on. Full answers remain visible in the terminal; spoken answers are
   shortened. Speech recognition and synthesis use the CPU and do not require a GPU.

The CLI stores conversation history and notes in `data/divyaraj.db` by default.
The web search tool uses DuckDuckGo and returns up to three results.

The Ollama Python SDK provides local chat and function calling; `httpx` is used to
report Ollama connection failures clearly; `duckduckgo-search` provides the free web
search integration. Voice input uses `faster-whisper`, NumPy, and `sounddevice`;
speech output uses offline `piper-tts` with a `pyttsx3` fallback.
