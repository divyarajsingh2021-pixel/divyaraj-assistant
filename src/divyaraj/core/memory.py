"""In-process conversation memory."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Message:
    """One message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str


class Memory:
    """Store user and assistant messages for the current process."""

    def __init__(self) -> None:
        """Initialize an empty in-memory conversation."""
        self._messages: list[Message] = []

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self._messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the conversation."""
        self._messages.append(Message(role="assistant", content=content))

    def history(self) -> tuple[Message, ...]:
        """Return an immutable snapshot of the conversation history."""
        return tuple(self._messages)
