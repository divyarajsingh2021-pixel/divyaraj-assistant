"""Text-only command-line interface."""

from divyaraj.core.agent import Agent
from divyaraj.core.tools.get_time import GetTimeTool  # noqa: F401
from divyaraj.core.tools.registry import get_tool


def main() -> None:
    """Run the interactive text-only assistant."""
    agent = Agent()
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
        print(agent.respond(message))


if __name__ == "__main__":
    main()
