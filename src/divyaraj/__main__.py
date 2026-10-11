"""Text and voice command-line interface."""

import argparse
import sys

from divyaraj.config import load_settings
from divyaraj.core.agent import Agent
from divyaraj.core.llm import OllamaClient, OllamaUnavailableError
from divyaraj.core.replies import format_tool_reply
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import get_tool
from divyaraj.stt import (
    SpeechToText,
    VoiceInputError,
    is_low_confidence_transcript,
)
from divyaraj.tts import SpeechOutputError, TextToSpeech


def _confirm_tool(tool: Tool) -> bool:
    """Prompt the CLI user to approve execution of a risky tool."""
    try:
        answer = input(f"Allow risky action '{tool.name}'? [y/N] ").strip().casefold()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def main() -> None:
    """Run the interactive text-only assistant."""
    parser = argparse.ArgumentParser(description="Chat with Divyaraj Assistant.")
    parser.add_argument("--model", help="Ollama model name for this run.")
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Use push-to-talk speech input and offline speech output.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open the desktop chat window.",
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.model:
        settings = settings.model_copy(update={"ollama_model": args.model})
    if args.gui:
        from divyaraj.ui_desktop.app import run_desktop

        run_desktop(settings)
        return

    agent = Agent(
        llm=OllamaClient(settings),
        confirmation_callback=_confirm_tool,
    )
    print(f"Model: {settings.ollama_model}")
    if args.voice:
        print(
            f"Speech recognition model: {settings.whisper_model} "
            f"(CPU, {settings.stt_compute_type})"
        )
        print("Divyaraj Assistant (voice mode). Enter starts push-to-talk.")
        _voice_loop(agent, SpeechToText(settings), TextToSpeech(settings))
        return

    print("Divyaraj Assistant (text mode). Type /time or 'exit' to quit.")
    while True:
        try:
            message = input("> ").strip()
        except EOFError:
            print()
            break

        if message.lower() in {"exit", "quit"}:
            break
        if not message:
            continue
        if message == "/time":
            print(format_tool_reply("get_time", get_tool("get_time").run({})))
            continue
        try:
            print(agent.respond(message))
        except OllamaUnavailableError as error:
            print(
                f"{error}\nStart Ollama and run 'ollama pull {settings.ollama_model}'.",
                file=sys.stderr,
            )


def _voice_loop(
    agent: Agent,
    speech_to_text: SpeechToText,
    text_to_speech: TextToSpeech,
) -> None:
    """Handle push-to-talk turns, mute commands, and spoken responses."""
    muted = False
    while True:
        try:
            command = input("Enter to talk, /mute, /unmute, or exit: ").strip()
        except EOFError:
            print()
            return

        normalized_command = command.casefold()
        if normalized_command in {"exit", "quit", "/exit"}:
            return
        if normalized_command == "/mute":
            muted = True
            print("Spoken replies are muted.")
            continue
        if normalized_command == "/unmute":
            muted = False
            print("Spoken replies are on.")
            continue
        if command:
            print("Press Enter to start push-to-talk, or use /mute or exit.")
            continue

        try:
            transcript = speech_to_text.listen(started=True)
            message = transcript.text.strip()
            if is_low_confidence_transcript(transcript):
                print("Sorry, I didn't catch that. Please say it again.")
                continue
            print(f"You: {message}")
            if message.casefold() in {"/mute", "/unmute"}:
                muted = message.casefold() == "/mute"
                print(
                    "Spoken replies are muted." if muted else "Spoken replies are on."
                )
                continue
            reply = agent.respond(message)
            print(reply)
            text_to_speech.speak(reply, muted=muted)
        except VoiceInputError as error:
            print(str(error), file=sys.stderr)
        except OllamaUnavailableError as error:
            print(
                f"{error}\nStart Ollama and make sure your configured model is pulled.",
                file=sys.stderr,
            )
        except SpeechOutputError as error:
            print(str(error), file=sys.stderr)


if __name__ == "__main__":
    main()
