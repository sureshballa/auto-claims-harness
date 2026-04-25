"""Tests for evals/null_agent.py."""

import pytest

from evals.agent_protocol import AgentRunResult, EvalAgent
from evals.null_agent import NullAgent
from evals.scenarios import ExpectedDecision, ExpectedTier, Scenario

_SCENARIO = Scenario(
    id="green-001-clean-collision",
    name="Clean collision",
    description="Low-damage collision; no injuries.",
    claim_number="CLM-001",
    expected_tier=ExpectedTier.GREEN,
    expected_decision=ExpectedDecision.APPROVE,
)


def test_null_agent_satisfies_protocol() -> None:
    """NullAgent must be recognized as an EvalAgent by the runtime-checkable Protocol."""
    assert isinstance(NullAgent(), EvalAgent)


@pytest.mark.asyncio
async def test_null_agent_run_returns_escalation() -> None:
    """run_scenario must always return a well-formed escalation result."""
    result = await NullAgent().run_scenario(_SCENARIO)

    assert isinstance(result, AgentRunResult)
    assert result.decision == ExpectedDecision.ESCALATE
    assert result.tier_assigned is None
    assert result.payout_amount is None
    assert result.tool_calls_made == []
    assert result.error is None
    assert _SCENARIO.id in result.reasoning


@pytest.mark.asyncio
async def test_null_agent_is_deterministic() -> None:
    """Same scenario in, identical result out, every time."""
    agent = NullAgent()
    first = await agent.run_scenario(_SCENARIO)
    second = await agent.run_scenario(_SCENARIO)
    assert first == second
