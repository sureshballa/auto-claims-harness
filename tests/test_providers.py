"""Tests for harness/providers.py.

These tests never make real network calls. They verify factory branching,
error handling, and the concrete type of client returned. All environment
variables are set via monkeypatch; nothing leaks from the real environment.
"""

import pytest

from harness.providers import ProviderConfigError, build_chat_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LMSTUDIO_ENV = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/",
    "LMSTUDIO_MODEL": "openai/gpt-oss-20b",
}
_ANTHROPIC_ENV = {
    "ANTHROPIC_API_KEY": "fake-key",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5-20250929",
}
_OPENAI_ENV = {
    "OPENAI_API_KEY": "fake-openai-key",
    "OPENAI_MODEL": "gpt-4o",
}


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all provider-related vars so tests start from a clean slate."""
    for var in (
        "LLM_PROVIDER",
        "LMSTUDIO_BASE_URL",
        "LMSTUDIO_MODEL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_default_provider_is_lmstudio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Omitting LLM_PROVIDER should fall back to lmstudio."""
    _clean_env(monkeypatch)
    for k, v in _LMSTUDIO_ENV.items():
        monkeypatch.setenv(k, v)

    from agent_framework.openai import OpenAIChatClient

    try:
        client = build_chat_client()
    except Exception as exc:
        raise AssertionError(
            f"build_chat_client() raised unexpectedly for lmstudio default: {exc!r}"
        ) from exc

    assert isinstance(client, OpenAIChatClient), f"Expected OpenAIChatClient, got {type(client)}"


def test_explicit_lmstudio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit LLM_PROVIDER=lmstudio should return an OpenAIChatClient."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    for k, v in _LMSTUDIO_ENV.items():
        monkeypatch.setenv(k, v)

    from agent_framework.openai import OpenAIChatClient

    try:
        client = build_chat_client()
    except Exception as exc:
        raise AssertionError(
            f"build_chat_client() raised unexpectedly for explicit lmstudio: {exc!r}"
        ) from exc

    assert isinstance(client, OpenAIChatClient), f"Expected OpenAIChatClient, got {type(client)}"


def test_anthropic_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=anthropic should return an AnthropicClient."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    for k, v in _ANTHROPIC_ENV.items():
        monkeypatch.setenv(k, v)

    from agent_framework.anthropic import AnthropicClient

    try:
        client = build_chat_client()
    except Exception as exc:
        raise AssertionError(
            f"build_chat_client() raised unexpectedly for anthropic: {exc!r}"
        ) from exc

    assert isinstance(client, AnthropicClient), f"Expected AnthropicClient, got {type(client)}"


def test_openai_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=openai should return an OpenAIChatClient."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    for k, v in _OPENAI_ENV.items():
        monkeypatch.setenv(k, v)

    from agent_framework.openai import OpenAIChatClient

    try:
        client = build_chat_client()
    except Exception as exc:
        raise AssertionError(
            f"build_chat_client() raised unexpectedly for openai: {exc!r}"
        ) from exc

    assert isinstance(client, OpenAIChatClient), f"Expected OpenAIChatClient, got {type(client)}"


# ---------------------------------------------------------------------------
# Unrecognized provider
# ---------------------------------------------------------------------------


def test_unrecognized_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown provider value must raise ProviderConfigError with context."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "grok")

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    msg = str(exc_info.value)
    assert "grok" in msg, f"Expected 'grok' in error message, got: {msg!r}"
    # Must tell the caller what the valid options are.
    for valid in ("lmstudio", "anthropic", "openai"):
        assert valid in msg, f"Expected '{valid}' listed in error message, got: {msg!r}"


# ---------------------------------------------------------------------------
# Missing required env vars — lmstudio
# ---------------------------------------------------------------------------


def test_lmstudio_missing_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LMSTUDIO_MODEL", "openai/gpt-oss-20b")
    # LMSTUDIO_BASE_URL intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "LMSTUDIO_BASE_URL" in str(exc_info.value)


def test_lmstudio_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1/")
    # LMSTUDIO_MODEL intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "LMSTUDIO_MODEL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Missing required env vars — anthropic
# ---------------------------------------------------------------------------


def test_anthropic_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    # ANTHROPIC_API_KEY intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


def test_anthropic_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    # ANTHROPIC_MODEL intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "ANTHROPIC_MODEL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Missing required env vars — openai
# ---------------------------------------------------------------------------


def test_openai_missing_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    # OPENAI_API_KEY intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_openai_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    # OPENAI_MODEL intentionally absent

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "OPENAI_MODEL" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_string_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whitespace-only env var must be treated the same as missing."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "   ")  # whitespace only
    monkeypatch.setenv("LMSTUDIO_MODEL", "openai/gpt-oss-20b")

    with pytest.raises(ProviderConfigError) as exc_info:
        build_chat_client()

    assert "LMSTUDIO_BASE_URL" in str(exc_info.value)


def test_provider_value_with_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER with surrounding whitespace should still match correctly."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "  lmstudio  ")
    for k, v in _LMSTUDIO_ENV.items():
        monkeypatch.setenv(k, v)

    from agent_framework.openai import OpenAIChatClient

    try:
        client = build_chat_client()
    except ProviderConfigError as exc:
        raise AssertionError(
            f"build_chat_client() raised ProviderConfigError for whitespace-padded provider: {exc!r}"
        ) from exc

    assert isinstance(client, OpenAIChatClient)
