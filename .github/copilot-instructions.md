# Copilot Instructions for Divyaraj Assistant

## Project overview
Divyaraj is a voice-first personal AI assistant (Ultron/Jarvis style). The user talks to it,
and it understands, decides, and performs tasks using tools, then replies by voice.
It is a free, open-source Python project, shipped as a Windows desktop app and an
Android-installable PWA client.

## Hard rules
- Use only free and open-source libraries and services. No paid APIs, no paid hosting.
- Never hardcode secrets or API keys. Read them from environment variables or a local
  config file that is listed in .gitignore.
- Python 3.11, type hints everywhere, docstrings on public functions.
- Keep functions small and single-purpose. Prefer clear code over clever code.
- Every new module must come with pytest tests. Mock audio, network, and LLM calls.
- Do not add a dependency without saying why, and add it to pyproject.toml.

## Architecture
- `src/divyaraj/core/`: agent loop, LLM client, memory, safety. No UI code here.
- `src/divyaraj/core/tools/`: one file per tool, registered with a shared registry.
- `src/divyaraj/stt.py` / `tts.py`: speech-to-text (faster-whisper) and text-to-speech (Piper, with pyttsx3 fallback).
- `src/divyaraj/api/`: FastAPI server with token authentication (used by the PWA).
- `src/divyaraj/ui_desktop/`: CustomTkinter app, system tray (pystray), global hotkey.
- `src/divyaraj/web/`: PWA client (manifest.json, service worker, Web Speech API).
- `packaging/`: PyInstaller spec and Inno Setup script.
- `tests/`: mirrors the src structure.

## Tool system
- Each tool has: name, description, JSON schema for arguments, and a `run()` method.
- Tools are exposed to the LLM through function/tool calling.
- Tools that delete, send, install, or change system settings are marked `risky=True`
  and MUST ask the user for explicit confirmation before running.
- Email tools only create drafts. They never send automatically.

## LLM and voice
- Default brain: local model through Ollama. Optional fallback: Gemini free API.
- Support Hindi, English, and Hinglish input.
- Keep spoken replies short and natural. Put long details in the chat window instead.
- Provide a text-only mode so everything can be tested without a microphone.

## Code style
- Format with ruff. Lint must pass before committing.
- Use `logging`, not `print`, outside of the CLI entry point.
- Handle errors clearly: tell the user what failed and how to fix it, never crash silently.

## Git and workflow
- Work in small steps: one module per change, then run tests.
- Commit style: `feat: add note tool`, `fix: handle empty mic input`, `test: ...`.
- Update README.md when behavior or setup changes.

## When generating code
1. Briefly explain the plan before writing large changes.
2. Write the code and its tests together.
3. Mention anything I should run or install manually.
4. Do not rewrite unrelated files.