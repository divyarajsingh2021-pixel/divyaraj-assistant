"""Top-level text conversation orchestration."""

from divyaraj.core.llm import LLMClient
from divyaraj.core.memory import Memory


class Agent:
    """Coordinate a language model and conversation memory."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        memory: Memory | None = None,
    ) -> None:
        """Create an agent with default stub components when none are provided."""
        self.llm = llm or LLMClient()
        self.memory = memory or Memory()

    def respond(self, message: str) -> str:
        """Return a response to a non-empty user message and store the exchange."""
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("Message must not be empty.")

        self.memory.add_user_message(normalized_message)
        response = self.llm.generate(normalized_message)
        self.memory.add_assistant_message(response)
        return response
