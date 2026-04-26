"""Tests for harness/middleware/response_normalizer.py.

No LLM calls are made. _normalize_text() is exercised directly for unit
coverage of the transformation logic. normalize() is exercised for counter
behaviour. process() no longer exists — normalization is now called directly
by the agent (see agents/fnol_agent.py), not via MAF middleware.
"""

from __future__ import annotations

import json

from harness.middleware.response_normalizer import (
    _DEFAULT_VALUES,
    ResponseNormalizer,
)


def _make_n() -> ResponseNormalizer:
    return ResponseNormalizer()


# ---------------------------------------------------------------------------
# _normalize_text — transformation logic (no counters touched)
# ---------------------------------------------------------------------------

def test_strips_harmony_prefix() -> None:
    n = ResponseNormalizer()
    raw = '<|channel|>final <|constrain|>JSON<|message|>{"tier": "green"}'
    result = n.normalize(raw)
    assert result is not None
    parsed = json.loads(result)
    assert parsed["tier"] == "green"
    assert n.harmony_prefix_strips == 1


def test_strips_harmony_prefix_then_fences() -> None:
    n = ResponseNormalizer()
    raw = '<|channel|>final<|message|>```json\n{"tier": "green"}\n```'
    result = n.normalize(raw)
    assert result is not None
    assert n.harmony_prefix_strips == 1
    assert n.fence_strips == 1

def test_strips_markdown_fences() -> None:
    """Markdown-fenced JSON is unwrapped and the fence counter incremented.

    _normalize_text always applies defaults after stripping, so the output
    dict will contain more than just {"x": 1} — we assert only the structural
    facts this test is responsible for.
    """
    n = _make_n()
    result = n._normalize_text('```json\n{"x": 1}\n```')

    assert result is not None
    parsed = json.loads(result)
    assert parsed["x"] == 1          # original key preserved
    assert n.fence_strips == 1        # fence was stripped
    assert n.field_renames == 0       # no aliasing involved


def test_aliases_field_name() -> None:
    """An aliased field name is renamed to the canonical AgentDecision field."""
    n = _make_n()
    result = n._normalize_text('{"amount_paid": 100}')

    assert result is not None
    parsed = json.loads(result)
    assert "payout_amount" in parsed
    assert parsed["payout_amount"] == 100
    assert "amount_paid" not in parsed
    assert n.field_renames == 1


def test_drops_invented_fields() -> None:
    """Fields in the alias map with a None target are removed from the output."""
    n = _make_n()
    result = n._normalize_text('{"claim_id": "X", "tier": "green"}')

    assert result is not None
    parsed = json.loads(result)
    assert "claim_id" not in parsed
    assert parsed["tier"] == "green"
    assert n.field_drops == 1


def test_applies_defaults() -> None:
    """Missing required fields receive their configured default values."""
    n = _make_n()
    result = n._normalize_text('{"tier": "green", "decision": "approve"}')

    assert result is not None
    parsed = json.loads(result)
    assert parsed["payout_amount"] == _DEFAULT_VALUES["payout_amount"]
    assert parsed["reasoning"] == _DEFAULT_VALUES["reasoning"]
    assert n.field_defaults_applied == 2


def test_invalid_json_returns_none() -> None:
    """Unparseable text returns None; no transformation counters are touched."""
    n = _make_n()
    result = n._normalize_text("not json at all")

    assert result is None
    assert n.fence_strips == 0
    assert n.field_renames == 0
    assert n.normalizations_succeeded == 0


def test_list_at_top_level_returns_none() -> None:
    """A JSON array at the top level is not a normalizable object; return None."""
    n = _make_n()
    result = n._normalize_text("[1, 2, 3]")

    assert result is None


def test_passthrough_for_already_clean_input() -> None:
    """Valid AgentDecision JSON passes through with no transformation counters set."""
    n = _make_n()
    clean = '{"tier":"green","decision":"approve","payout_amount":0.0,"reasoning":"all good"}'
    result = n._normalize_text(clean)

    assert result is not None
    assert json.loads(result) == json.loads(clean)
    assert n.fence_strips == 0
    assert n.field_renames == 0
    assert n.field_drops == 0
    assert n.field_defaults_applied == 0


# ---------------------------------------------------------------------------
# normalize() — public API; wraps _normalize_text and manages counters
# ---------------------------------------------------------------------------


def test_normalize_increments_counters_on_success() -> None:
    """normalize() increments runs_processed and normalizations_succeeded on parseable input."""
    n = _make_n()
    result = n.normalize('{"tier": "green"}')

    assert result is not None
    assert n.runs_processed == 1
    assert n.normalizations_succeeded == 1
    assert n.normalizations_failed == 0


def test_normalize_increments_counters_on_failure() -> None:
    """normalize() increments runs_processed and normalizations_failed on unparseable input."""
    n = _make_n()
    result = n.normalize("not json at all")

    assert result is None
    assert n.runs_processed == 1
    assert n.normalizations_succeeded == 0
    assert n.normalizations_failed == 1
