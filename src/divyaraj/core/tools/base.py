"""Base class for assistant tools."""

from abc import ABC, abstractmethod


class Tool(ABC):
    """Describe and execute one assistant tool."""

    name: str
    description: str
    args_schema: dict[str, object]
    risky: bool = False

    @abstractmethod
    def run(self, arguments: dict[str, object]) -> str:
        """Run the tool with validated arguments and return a text result."""
