"""Tests for harness/middleware/response_normalizer.py.

No LLM calls are made. _normalize_text() is exercised directly for unit
coverage of the transformation logic. normalize() is exercised for counter
behaviour. process() no longer exists — normalization is now called directly
by the agent (see agents/fnol_agent.py), not via MAF middleware.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.middleware.response_normalizer import ResponseNormalizer
from harness.policy_engine import load_permissions
from harness.policy_engine.permissions_loader import ResponseNormalizerConfig

_PERMISSIONS_PATH = Path(__file__).parent.parent / "config" / "permissions.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def normalizer_config() -> ResponseNormalizerConfig:
    return load_permissions(_PERMISSIONS_PATH).response_normalizer


@pytest.fixture
def normalizer(normalizer_config: ResponseNormalizerConfig) -> ResponseNormalizer:
    return ResponseNormalizer(normalizer_config)


# ---------------------------------------------------------------------------
# _normalize_text — transformation logic (no counters touched by the public API)
# ---------------------------------------------------------------------------


def test_strips_harmony_prefix(normalizer: ResponseNormalizer) -> None:
    raw = '<|channel|>final <|constrain|>JSON<|message|>{"tier": "green"}'
    result = normalizer.normalize(raw)
    assert result is not None
    parsed = json.loads(result)
    assert parsed["tier"] == "green"
    assert normalizer.harmony_prefix_strips == 1


def test_strips_harmony_prefix_then_fences(normalizer: ResponseNormalizer) -> None:
    raw = '<|channel|>final<|message|>```json\n{"tier": "green"}\n```'
    result = normalizer.normalize(raw)
    assert result is not None
    assert normalizer.harmony_prefix_strips == 1
    assert normalizer.fence_strips == 1


def test_strips_markdown_fences(normalizer: ResponseNormalizer) -> None:
    """Markdown-fenced JSON is unwrapped and the fence counter incremented.

    _normalize_text always applies defaults after stripping, so the output
    dict will contain more than just {"x": 1} — we assert only the structural
    facts this test is responsible for.
    """
    result = normalizer._normalize_text('```json\n{"x": 1}\n```')

    assert result is not None
    parsed = json.loads(result)
    assert parsed["x"] == 1          # original key preserved
    assert normalizer.fence_strips == 1        # fence was stripped
    assert normalizer.field_renames == 0       # no aliasing involved


def test_aliases_field_name(normalizer: ResponseNormalizer) -> None:
    """An aliased field name is renamed to the canonical AgentDecision field."""
    result = normalizer._normalize_text('{"amount_paid": 100}')

    assert result is not None
    parsed = json.loads(result)
    assert "payout_amount" in parsed
    assert parsed["payout_amount"] == 100
    assert "amount_paid" not in parsed
    assert normalizer.field_renames == 1


def test_drops_invented_fields(normalizer: ResponseNormalizer) -> None:
    """Fields in the alias map with a None target are removed from the output."""
    result = normalizer._normalize_text('{"claim_id": "X", "tier": "green"}')

    assert result is not None
    parsed = json.loads(result)
    assert "claim_id" not in parsed
    assert parsed["tier"] == "green"
    assert normalizer.field_drops == 1


def test_applies_defaults(
    normalizer: ResponseNormalizer, normalizer_config: ResponseNormalizerConfig
) -> None:
    """Missing required fields receive their configured default values."""
    result = normalizer._normalize_text('{"tier": "green", "decision": "approve"}')

    assert result is not None
    parsed = json.loads(result)
    assert parsed["payout_amount"] == normalizer_config.defaults["payout_amount"]
    assert parsed["reasoning"] == normalizer_config.defaults["reasoning"]
    assert normalizer.field_defaults_applied == 2


def test_applies_defaults_when_field_is_explicitly_null(
    normalizer: ResponseNormalizer, normalizer_config: ResponseNormalizerConfig
) -> None:
    """An explicit null for a defaulted field is treated like a missing field."""
    result = normalizer._normalize_text(
        '{"tier": null, "decision": "escalate"}'
    )

    assert result is not None
    parsed = json.loads(result)
    assert parsed["tier"] == normalizer_config.defaults["tier"]
    assert normalizer.field_defaults_applied >= 1


def test_invalid_json_returns_none(normalizer: ResponseNormalizer) -> None:
    """Unparseable text returns None; no transformation counters are touched."""
    result = normalizer._normalize_text("not json at all")

    assert result is None
    assert normalizer.fence_strips == 0
    assert normalizer.field_renames == 0
    assert normalizer.normalizations_succeeded == 0


def test_list_at_top_level_returns_none(normalizer: ResponseNormalizer) -> None:
    """A JSON array at the top level is not a normalizable object; return None."""
    result = normalizer._normalize_text("[1, 2, 3]")

    assert result is None


def test_passthrough_for_already_clean_input(normalizer: ResponseNormalizer) -> None:
    """Valid AgentDecision JSON passes through with no transformation counters set."""
    clean = '{"tier":"green","decision":"approve","payout_amount":0.0,"reasoning":"all good"}'
    result = normalizer._normalize_text(clean)

    assert result is not None
    assert json.loads(result) == json.loads(clean)
    assert normalizer.fence_strips == 0
    assert normalizer.field_renames == 0
    assert normalizer.field_drops == 0
    assert normalizer.field_defaults_applied == 0


# ---------------------------------------------------------------------------
# normalize() — public API; wraps _normalize_text and manages counters
# ---------------------------------------------------------------------------


def test_normalize_increments_counters_on_success(normalizer: ResponseNormalizer) -> None:
    """normalize() increments runs_processed and normalizations_succeeded on parseable input."""
    result = normalizer.normalize('{"tier": "green"}')

    assert result is not None
    assert normalizer.runs_processed == 1
    assert normalizer.normalizations_succeeded == 1
    assert normalizer.normalizations_failed == 0


def test_normalize_increments_counters_on_failure(normalizer: ResponseNormalizer) -> None:
    """normalize() increments runs_processed and normalizations_failed on unparseable input."""
    result = normalizer.normalize("not json at all")

    assert result is None
    assert normalizer.runs_processed == 1
    assert normalizer.normalizations_succeeded == 0
    assert normalizer.normalizations_failed == 1
