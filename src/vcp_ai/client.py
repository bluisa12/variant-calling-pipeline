"""The single place that talks to the LLM provider.

Keeping all network calls here means switching provider (FreeLLMAPI, Gemini
directly, or another model) only changes this file.

Not implemented yet: waiting on FreeLLMAPI's request format (OpenAI-compatible
or not) and the exact model name. See README, "Optional AI steps".
"""

from __future__ import annotations

from .config import AISettings


class LLMClient:
    def __init__(self, settings: AISettings):
        if not settings.enabled:
            raise RuntimeError("AI steps are disabled. Set ai.enabled: true in config/config.yaml.")
        self.settings = settings

    def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt and return the model's text reply."""
        raise NotImplementedError(
            "LLMClient.complete is not implemented yet: FreeLLMAPI's endpoint format "
            "still needs to be confirmed."
        )
