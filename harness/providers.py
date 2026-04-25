"""Single chat-client factory for the auto-claims harness.

This module is the only place in the project that knows how to construct MAF
chat clients. It reads provider selection and credentials from environment
variables and returns a MAF client instance ready for use as
``client.create_agent(...)``.

No retry, circuit-breaker, or wrapping logic lives here — those are middleware
concerns (see ``harness/middleware/``). Each call to ``build_chat_client()``
constructs a fresh client; caching is the caller's responsibility.
"""

import os
from typing import Any, Final, Literal

Provider = Literal["lmstudio", "anthropic", "openai"]
_VALID_PROVIDERS: Final[tuple[str, ...]] = ("lmstudio", "anthropic", "openai")


class ProviderConfigError(ValueError):
    """Raised when LLM provider configuration in the environment is invalid or incomplete."""


def _required_env(name: str) -> str:
    """Return the named environment variable, raising if missing or empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ProviderConfigError(f"Required environment variable {name} is missing or empty")
    return value


def build_chat_client() -> Any:
    """Construct a MAF chat client based on environment configuration.

    Reads:
        LLM_PROVIDER: one of "lmstudio", "anthropic", "openai".
                     Defaults to "lmstudio" if unset.

        For LM Studio:
            LMSTUDIO_BASE_URL: required (e.g., "http://localhost:1234/v1/")
            LMSTUDIO_MODEL: required (e.g., "openai/gpt-oss-20b")

        For Anthropic:
            ANTHROPIC_API_KEY: required
            ANTHROPIC_MODEL: required (e.g., "claude-sonnet-4-5-20250929")

        For OpenAI:
            OPENAI_API_KEY: required
            OPENAI_MODEL: required (e.g., "gpt-4o")

    Returns:
        A MAF chat client. Concrete type varies by provider; callers should
        treat it as the MAF ChatClientProtocol surface (.create_agent(), etc.).

    Raises:
        ProviderConfigError: if LLM_PROVIDER is unrecognized, or required
            environment variables for the chosen provider are missing or empty.
    """
    provider = os.environ.get("LLM_PROVIDER", "lmstudio").strip()

    if provider not in _VALID_PROVIDERS:
        raise ProviderConfigError(
            f"LLM_PROVIDER={provider!r} is not recognized. "
            f"Valid values: {', '.join(_VALID_PROVIDERS)}"
        )

    if provider == "lmstudio":
        base_url = _required_env("LMSTUDIO_BASE_URL")
        model_id = _required_env("LMSTUDIO_MODEL")
        from agent_framework.openai import OpenAIChatClient

        # LM Studio accepts any non-empty string as api_key; the OpenAI SDK
        # requires the field to be present.
        return OpenAIChatClient(model=model_id, base_url=base_url, api_key="lm-studio")

    if provider == "anthropic":
        api_key = _required_env("ANTHROPIC_API_KEY")
        model_id = _required_env("ANTHROPIC_MODEL")
        from agent_framework.anthropic import AnthropicClient

        return AnthropicClient(api_key=api_key, model=model_id)

    # provider == "openai"
    api_key = _required_env("OPENAI_API_KEY")
    model_id = _required_env("OPENAI_MODEL")
    from agent_framework.openai import OpenAIChatClient

    return OpenAIChatClient(model=model_id, api_key=api_key)
