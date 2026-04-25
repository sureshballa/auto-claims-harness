"""Stub agent that satisfies EvalAgent with deterministic, do-nothing behavior.

NullAgent exists solely to give the eval runner something to drive before any
real agent is built. It escalates every claim unconditionally, makes no tool
calls, and never touches MAF, the network, or the filesystem.

Expected eval results when using NullAgent:
- 100% escalation rate regardless of expected_decision
- 0% tier accuracy (tier_assigned is always None)
- Near-zero payout accuracy (payout_amount is always None)

That outcome is intentional. A passing eval suite with NullAgent confirms the
runner pipeline is wired correctly, not that claims are being handled.
"""

from evals.agent_protocol import AgentRunResult, EvalAgent
from evals.scenarios import ExpectedDecision, Scenario


class NullAgent:
    """Deterministic stub: escalates every scenario, calls no tools."""

    async def run_scenario(self, scenario: Scenario) -> AgentRunResult:
        """Return a fixed escalation result for any scenario."""
        return AgentRunResult(
            tier_assigned=None,
            decision=ExpectedDecision.ESCALATE,
            payout_amount=None,
            tool_calls_made=[],
            reasoning=(
                f"NullAgent stub: I do not adjudicate claims. "
                f"Scenario {scenario.id} escalated by default."
            ),
            error=None,
        )


# Verify protocol conformance at import time so a structural break fails loudly.
_: EvalAgent = NullAgent()
