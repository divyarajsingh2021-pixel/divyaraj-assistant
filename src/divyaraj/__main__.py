"""Text-only command-line interface."""

import argparse
import sys

from divyaraj.config import load_settings
from divyaraj.core.agent import Agent
from divyaraj.core.llm import OllamaClient, OllamaUnavailableError
from divyaraj.core.tools.base import Tool
from divyaraj.core.tools.registry import get_tool


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
    args = parser.parse_args()

    settings = load_settings()
    if args.model:
        settings = settings.model_copy(update={"ollama_model": args.model})
    agent = Agent(
        llm=OllamaClient(settings),
        confirmation_callback=_confirm_tool,
    )
    print(f"Model: {settings.ollama_model}")
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
            print(get_tool("get_time").run({}))
            continue
        try:
            print(agent.respond(message))
        except OllamaUnavailableError as error:
            print(
                f"{error}\nStart Ollama and run 'ollama pull {settings.ollama_model}'.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
