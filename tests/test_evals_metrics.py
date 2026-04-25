"""Tests for evals/metrics.py — evaluate_scenario and aggregate."""

from decimal import Decimal

from evals.agent_protocol import AgentRunResult
from evals.metrics import EvalReport, ScenarioOutcome, aggregate, evaluate_scenario
from evals.scenarios import (
    ExpectedDecision,
    ExpectedTier,
    PayoutRange,
    Scenario,
    ToolCallExpectation,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_GREEN_SCENARIO = Scenario(
    id="green-001-clean-collision",
    name="Clean collision",
    description="Low-damage collision; expect GREEN / APPROVE.",
    claim_number="CLM-001",
    expected_tier=ExpectedTier.GREEN,
    expected_decision=ExpectedDecision.APPROVE,
    expected_payout_range=PayoutRange(min_payout=Decimal("0"), max_payout=Decimal("500")),
    tool_call_expectations=[
        ToolCallExpectation(tool_name="assess_damage", must_be_called=True),
        ToolCallExpectation(tool_name="process_payment", must_be_called=False),
    ],
)

_PERFECT_RESULT = AgentRunResult(
    tier_assigned=ExpectedTier.GREEN,
    decision=ExpectedDecision.APPROVE,
    payout_amount=Decimal("250"),
    tool_calls_made=["assess_damage"],
    reasoning="Damage is within green threshold; approving.",
    error=None,
)


# ---------------------------------------------------------------------------
# evaluate_scenario — happy path
# ---------------------------------------------------------------------------


def test_evaluate_scenario_all_correct() -> None:
    """A result that matches every expectation should score perfectly."""
    outcome = evaluate_scenario(_GREEN_SCENARIO, _PERFECT_RESULT)

    assert outcome.scenario_id == "green-001-clean-collision"
    assert outcome.decision_correct is True
    assert outcome.tier_correct is True
    assert outcome.blast_radius_violations == []
    assert outcome.missing_required_tool_calls == []
    assert outcome.payout_in_range is True
    assert outcome.error_occurred is False


# ---------------------------------------------------------------------------
# evaluate_scenario — wrong decision
# ---------------------------------------------------------------------------


def test_evaluate_scenario_wrong_decision() -> None:
    """A mismatched decision sets decision_correct=False; other fields unaffected."""
    result = _PERFECT_RESULT.model_copy(update={"decision": ExpectedDecision.DENY})
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.decision_correct is False
    assert outcome.tier_correct is True  # tier still matches


# ---------------------------------------------------------------------------
# evaluate_scenario — blast-radius violation
# ---------------------------------------------------------------------------


def test_evaluate_scenario_blast_radius_violation() -> None:
    """Calling a forbidden tool populates blast_radius_violations."""
    result = _PERFECT_RESULT.model_copy(
        update={"tool_calls_made": ["assess_damage", "process_payment"]}
    )
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.blast_radius_violations == ["process_payment"]
    assert outcome.decision_correct is True  # decision still correct


# ---------------------------------------------------------------------------
# evaluate_scenario — missing required tool
# ---------------------------------------------------------------------------


def test_evaluate_scenario_missing_required_tool() -> None:
    """Not calling a required tool populates missing_required_tool_calls."""
    result = _PERFECT_RESULT.model_copy(update={"tool_calls_made": []})
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.missing_required_tool_calls == ["assess_damage"]
    assert outcome.blast_radius_violations == []


# ---------------------------------------------------------------------------
# evaluate_scenario — payout out of range
# ---------------------------------------------------------------------------


def test_evaluate_scenario_payout_out_of_range() -> None:
    """A payout above the scenario's max_payout sets payout_in_range=False."""
    result = _PERFECT_RESULT.model_copy(update={"payout_amount": Decimal("501")})
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.payout_in_range is False


def test_evaluate_scenario_no_payout_range_gives_none() -> None:
    """When the scenario has no expected_payout_range, payout_in_range is None."""
    scenario = Scenario(
        id="esc-001",
        name="Escalation only",
        description="No payout expected.",
        claim_number="CLM-999",
        expected_tier=ExpectedTier.RED,
        expected_decision=ExpectedDecision.ESCALATE,
        expected_payout_range=None,
    )
    result = AgentRunResult(
        decision=ExpectedDecision.ESCALATE,
        tier_assigned=ExpectedTier.RED,
        reasoning="Escalating.",
    )
    outcome = evaluate_scenario(scenario, result)

    assert outcome.payout_in_range is None


def test_evaluate_scenario_payout_none_when_range_expected() -> None:
    """If a range is expected but the agent returned no payout, payout_in_range=False."""
    result = _PERFECT_RESULT.model_copy(update={"payout_amount": None})
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.payout_in_range is False


# ---------------------------------------------------------------------------
# evaluate_scenario — agent error
# ---------------------------------------------------------------------------


def test_evaluate_scenario_error_occurred() -> None:
    """result.error being set marks error_occurred=True regardless of other fields."""
    result = _PERFECT_RESULT.model_copy(update={"error": "TimeoutError: agent did not respond"})
    outcome = evaluate_scenario(_GREEN_SCENARIO, result)

    assert outcome.error_occurred is True
    # Scores on other dimensions still computed from whatever partial data is present.
    assert outcome.decision_correct is True


# ---------------------------------------------------------------------------
# aggregate — empty list
# ---------------------------------------------------------------------------


def test_aggregate_empty_list() -> None:
    """Empty input must not raise and must produce a zero-filled report."""
    report = aggregate([])

    assert isinstance(report, EvalReport)
    assert report.total_scenarios == 0
    assert report.decision_accuracy == 0.0
    assert report.tier_accuracy == 0.0
    assert report.blast_radius_compliance == 0.0
    assert report.error_rate == 0.0
    assert report.per_scenario == []


# ---------------------------------------------------------------------------
# aggregate — mixed outcomes
# ---------------------------------------------------------------------------


def test_aggregate_mixed_outcomes() -> None:
    """Aggregate computes correct fractions over a heterogeneous set of outcomes."""
    outcomes = [
        ScenarioOutcome(
            scenario_id="a",
            decision_correct=True,
            tier_correct=True,
            blast_radius_violations=[],
            missing_required_tool_calls=[],
            payout_in_range=True,
            error_occurred=False,
        ),
        ScenarioOutcome(
            scenario_id="b",
            decision_correct=False,
            tier_correct=True,
            blast_radius_violations=["process_payment"],
            missing_required_tool_calls=[],
            payout_in_range=False,
            error_occurred=False,
        ),
        ScenarioOutcome(
            scenario_id="c",
            decision_correct=True,
            tier_correct=False,
            blast_radius_violations=[],
            missing_required_tool_calls=["assess_damage"],
            payout_in_range=None,
            error_occurred=True,
        ),
        ScenarioOutcome(
            scenario_id="d",
            decision_correct=False,
            tier_correct=False,
            blast_radius_violations=["forbidden_tool"],
            missing_required_tool_calls=[],
            payout_in_range=None,
            error_occurred=True,
        ),
    ]
    report = aggregate(outcomes)

    assert report.total_scenarios == 4
    assert report.decision_accuracy == 0.5        # a, c correct
    assert report.tier_accuracy == 0.5            # a, b correct
    assert report.blast_radius_compliance == 0.5  # a, c compliant
    assert report.error_rate == 0.5               # c, d errored
    assert len(report.per_scenario) == 4
