"""Language-model client placeholder."""


class LLMClient:
    """Deterministic local stub to keep the initial CLI usable without a model."""

    def generate(self, prompt: str) -> str:
        """Generate a short placeholder response for a user prompt."""
        return f"I heard you: {prompt}"
