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

3. Create a Python 3.11 virtual environment and install the project:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```

4. Optionally copy `.env.example` to `.env` and set `OLLAMA_MODEL`,
   `OLLAMA_BASE_URL`, `DATA_DIR`, or `ALLOWED_APPS`. `ALLOWED_APPS` is a JSON
   object mapping approved app names to executable paths.
5. Run the text CLI:

   ```powershell
   python -m divyaraj
   ```

   Use `python -m divyaraj --model qwen2.5:3b` to select a model for one run.
   Type `exit` to quit. Risky tool calls ask for confirmation before execution.

The CLI stores conversation history and notes in `data/divyaraj.db` by default.
The web search tool uses DuckDuckGo and returns up to three results.

The Ollama Python SDK provides local chat and function calling; `httpx` is used to
report Ollama connection failures clearly; `duckduckgo-search` provides the free web
search integration.
