"""Tests for evals/scenarios.py — schema construction, YAML loading, and sorting.

YAML fixture data lives in evals/scenario_files/; this test module uses
tmp_path for isolation and does not read from that directory.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from evals.scenarios import (
    ExpectedDecision,
    ExpectedTier,
    PayoutRange,
    Scenario,
    ScenarioParseError,
    ToolCallExpectation,
    load_all_scenarios,
    load_scenario,
)

# ---------------------------------------------------------------------------
# Direct model construction
# ---------------------------------------------------------------------------


def test_scenario_minimal_valid() -> None:
    """Required-only fields should construct without error; optional fields default cleanly."""
    s = Scenario(
        id="green-001-clean-collision",
        name="Clean collision — green tier",
        description="Low-damage collision with no injuries; expect GREEN tier and APPROVE.",
        claim_number="CLM-001",
        expected_tier=ExpectedTier.GREEN,
        expected_decision=ExpectedDecision.APPROVE,
    )
    assert s.id == "green-001-clean-collision"
    assert s.tags == []
    assert s.claimant_message is None
    assert s.expected_payout_range is None
    assert s.tool_call_expectations == []


def test_scenario_full_valid() -> None:
    """All optional fields populated should also construct without error."""
    s = Scenario(
        id="green-001-clean-collision",
        name="Clean collision — green tier",
        description="Low-damage collision with no injuries; expect GREEN tier and APPROVE.",
        claim_number="CLM-001",
        expected_tier=ExpectedTier.GREEN,
        expected_decision=ExpectedDecision.APPROVE,
        tags=["green", "fnol", "collision"],
        claimant_message="I was rear-ended at a stoplight.",
        expected_payout_range=PayoutRange(min_payout=Decimal("0"), max_payout=Decimal("500")),
        tool_call_expectations=[
            ToolCallExpectation(tool_name="assess_damage", must_be_called=True),
            ToolCallExpectation(tool_name="escalate_to_human", must_be_called=False),
        ],
    )
    assert s.tags == ["green", "fnol", "collision"]
    assert s.expected_payout_range is not None
    assert s.expected_payout_range.max_payout == Decimal("500")
    assert len(s.tool_call_expectations) == 2


def test_payout_range_max_must_exceed_min() -> None:
    """max_payout < min_payout is an authoring error and must be rejected."""
    with pytest.raises(ValidationError, match="max_payout"):
        PayoutRange(min_payout=Decimal("1000"), max_payout=Decimal("999"))


def test_payout_range_negative_min_rejected() -> None:
    """Negative min_payout has no meaningful interpretation and must be rejected."""
    with pytest.raises(ValidationError):
        PayoutRange(min_payout=Decimal("-1"), max_payout=Decimal("500"))


# ---------------------------------------------------------------------------
# YAML loading — helpers
# ---------------------------------------------------------------------------

_MINIMAL_YAML = """\
id: green-001-clean-collision
name: Clean collision — green tier
description: Low-damage collision with no injuries.
claim_number: CLM-001
expected_tier: green
expected_decision: approve
"""

_FULL_YAML = """\
id: red-002-injury-escalation
name: Injury escalation — red tier
description: High-damage claim with injuries; should escalate.
claim_number: CLM-002
claimant_message: The other driver ran a red light and hit my car.
expected_tier: red
expected_decision: escalate
expected_payout_range:
  min_payout: "5000"
  max_payout: "25000"
tool_call_expectations:
  - tool_name: assess_damage
    must_be_called: true
  - tool_name: auto_approve
    must_be_called: false
tags:
  - red
  - injury
  - fnol
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# YAML loading — happy path
# ---------------------------------------------------------------------------


def test_load_scenario_from_yaml(tmp_path: Path) -> None:
    """A well-formed YAML file should deserialize into a correct Scenario."""
    f = _write(tmp_path / "green-001.yaml", _FULL_YAML)
    s = load_scenario(f)

    assert s.id == "red-002-injury-escalation"
    assert s.expected_tier == ExpectedTier.RED
    assert s.expected_decision == ExpectedDecision.ESCALATE
    assert s.claimant_message is not None
    assert s.expected_payout_range is not None
    assert s.expected_payout_range.min_payout == Decimal("5000")
    assert s.expected_payout_range.max_payout == Decimal("25000")
    assert len(s.tool_call_expectations) == 2
    assert s.tool_call_expectations[0].tool_name == "assess_damage"
    assert s.tool_call_expectations[0].must_be_called is True
    assert s.tool_call_expectations[1].must_be_called is False
    assert s.tags == ["red", "injury", "fnol"]


# ---------------------------------------------------------------------------
# YAML loading — error paths
# ---------------------------------------------------------------------------


def test_load_scenario_missing_required_field(tmp_path: Path) -> None:
    """YAML missing claim_number must raise ScenarioParseError, not a raw ValidationError."""
    yaml_without_claim_number = """\
id: broken-001
name: Broken scenario
description: Missing claim_number field.
expected_tier: green
expected_decision: approve
"""
    f = _write(tmp_path / "broken.yaml", yaml_without_claim_number)
    with pytest.raises(ScenarioParseError):
        load_scenario(f)


def test_load_scenario_invalid_enum(tmp_path: Path) -> None:
    """An unrecognised tier value must raise ScenarioParseError."""
    yaml_bad_tier = _MINIMAL_YAML.replace("expected_tier: green", "expected_tier: purple")
    f = _write(tmp_path / "bad-tier.yaml", yaml_bad_tier)
    with pytest.raises(ScenarioParseError):
        load_scenario(f)


# ---------------------------------------------------------------------------
# load_all_scenarios
# ---------------------------------------------------------------------------


def test_load_all_scenarios_returns_sorted(tmp_path: Path) -> None:
    """Scenarios are returned sorted by id regardless of filename order."""
    for scenario_id, filename in [
        ("z-001-last", "z-001.yaml"),
        ("a-001-first", "a-001.yaml"),
        ("m-001-middle", "m-001.yaml"),
    ]:
        content = f"""\
id: {scenario_id}
name: Scenario {scenario_id}
description: Sorting test fixture.
claim_number: CLM-SORT
expected_tier: green
expected_decision: approve
"""
        _write(tmp_path / filename, content)

    scenarios = load_all_scenarios(tmp_path)

    assert len(scenarios) == 3
    assert [s.id for s in scenarios] == ["a-001-first", "m-001-middle", "z-001-last"]


def test_load_all_scenarios_empty_dir(tmp_path: Path) -> None:
    """An empty directory should return an empty list without raising."""
    result = load_all_scenarios(tmp_path)
    assert result == []
