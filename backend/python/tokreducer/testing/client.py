"""LLMTestClient — thin wrapper around LLM APIs for integration tests."""

from __future__ import annotations

import os


class LLMTestClient:
    """Synchronous helper that calls an LLM and returns the text response.

    Parameters
    ----------
    provider:
        ``"openai"`` or ``"anthropic"``.
    model:
        Model name, e.g. ``"gpt-4o"``.
    api_key:
        Explicit key; falls back to the standard environment variable.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        key = os.environ.get(env_map.get(self.provider, ""), "")
        if not key:
            raise RuntimeError(
                f"No API key for {self.provider}. "
                f"Set {env_map.get(self.provider, 'API_KEY')}."
            )
        return key

    def ask(
        self,
        prompt: str,
        system: str | None = None,
    ) -> str:
        """Send *prompt* to the LLM and return the text response."""
        if self.provider == "openai":
            return self._ask_openai(prompt, system)
        if self.provider == "anthropic":
            return self._ask_anthropic(prompt, system)
        raise ValueError(f"Unsupported provider: {self.provider}")

    # ------------------------------------------------------------------
    # Provider implementations
    # ------------------------------------------------------------------

    def _ask_openai(self, prompt: str, system: str | None) -> str:
        import openai

        client = openai.OpenAI(api_key=self.api_key)
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    def _ask_anthropic(self, prompt: str, system: str | None) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        message = client.messages.create(**kwargs)
        return message.content[0].text  # type: ignore[union-attr]
