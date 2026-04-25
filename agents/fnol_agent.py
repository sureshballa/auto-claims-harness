"""Stage 1 naive agent for auto-insurance FNOL adjudication.

This is the first real agent in the harness. It satisfies the EvalAgent protocol
and uses MAF with the configured LLM to produce an AgentRunResult. It is
deliberately naive:

- No middleware (no retry, no circuit-breaker, no telemetry)
- No tools (no domain function calls beyond loading seed data)
- Single short instruction prompt (no chain-of-thought, no examples)
- Structured output from the LLM, unmarshal-and-map only

The failures this agent exhibits — missed tiers, wrong decisions on adversarial
inputs, fabricated payouts — are inputs to subsequent stage designs. Stage 1's
job is to expose what the harness needs to fix, not to be correct.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from agent_framework.openai import OpenAIChatOptions
from pydantic import BaseModel, ConfigDict, Field

from domain.mock_data import load_claims, load_policies
from domain.models import Claim, Policy
from evals.agent_protocol import AgentRunResult
from evals.scenarios import ExpectedDecision, ExpectedTier, Scenario
from harness.providers import build_chat_client

import json
import re


INSTRUCTIONS = """\
You are an auto-insurance claims adjudication assistant. Your job is to review
incoming First Notice of Loss (FNOL) claims and decide how each should be handled.

CLAIM TIERS
Assign one of these tiers based on damage severity and risk:
  green:  Low-damage, straightforward claim. Eligible for auto-approval.
  yellow: Moderate damage or complexity. Requires human review.
  red:    High-damage or significant liability. Requires senior adjuster review.
  black:  Catastrophic loss, fraud indicator, or extreme liability. Escalate immediately.

DECISIONS
Choose exactly one:
  approve:  Authorize payment for a covered loss within policy limits.
  deny:     Decline payment — policy not active, coverage exclusion, or fraud indicator.
  escalate: Forward to a human adjuster — missing information, ambiguity, or high-severity tier.

RULES
- If any required information is missing or unclear, choose ESCALATE rather than guess.
- Verify the policy covers the incident type before approving.
- Return your response as JSON exactly matching the AgentDecision schema provided.
"""
_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

def _strip_json_fences(text: str) -> str:
        """STAGE 1 PATCH — should move to middleware in Stage 2.
        
        Some open-weight models wrap JSON in markdown fences despite
        response_format. Strip them so json.loads succeeds.
        """
        match = _MARKDOWN_FENCE_RE.match(text.strip())
        return match.group(1) if match else text

class AgentDecision(BaseModel):
    """Structured response we ask the LLM to produce.

    Uses plain str fields rather than domain enums because the LLM is more
    likely to comply with simple string constraints than with typed enum members.
    Callers map these strings back to domain types after parsing.

    payout_amount is float here because LLM JSON output has no Decimal type.
    It is immediately converted to Decimal(str(...)) in run_scenario — never
    stored or used as float in domain logic.
    """

    model_config = ConfigDict(frozen=True)

    tier: str = Field(description="One of: green, yellow, red, black. Lowercase.")
    decision: str = Field(description="One of: approve, deny, escalate. Lowercase.")
    payout_amount: float = Field(
        description="Amount the insurer should pay, in USD. Use 0 for denials or escalations."
    )
    reasoning: str = Field(description="One-paragraph explanation of how you decided.")


def _render_claim_prompt(claim: Claim, policy: Policy | None) -> str:
    """Format a claim and optional policy as the LLM prompt body.

    If policy is None (adversarial scenario or lookup failure), the prompt
    states this explicitly so the agent can apply its escalation rule.
    """
    damage_str = (
        f"${claim.damage.assessed_amount:.2f} "
        f"(source: {claim.damage.assessment_source}, "
        f"confidence: {claim.damage.confidence})"
        if claim.damage is not None
        else "Not yet assessed"
    )

    lines = [
        "Please adjudicate the following claim.",
        "",
        f"Claim:                {claim.claim_number}",
        f"Policy:               {claim.policy_number}",
        f"Vehicle VIN:          {claim.vehicle_vin}",
        f"Incident type:        {claim.incident.incident_type}",
        f"Incident date:        {claim.incident.incident_date}",
        f"Description:          {claim.incident.description}",
        f"Location:             {claim.incident.location}",
        f"Injuries reported:    {str(claim.incident.injuries_reported).lower()}",
        f"Other parties:        {str(claim.incident.other_parties_involved).lower()}",
        f"Damage:               {damage_str}",
        "",
    ]

    if policy is None:
        lines += [
            "Policy details:       POLICY NOT FOUND — no active policy matches this claim number.",
            "                      Treat as an unverified claim; escalation is required.",
        ]
    else:
        coverage_lines = [
            f"    - {c.coverage_type.upper()}: "
            f"limit ${c.limit:.2f}, deductible ${c.deductible:.2f}"
            for c in policy.coverages
        ]
        active_str = (
            f"{policy.effective_date} to {policy.expiration_date}"
            f"{'' if policy.is_active else ' [EXPIRED]'}"
        )
        lines += [
            "Policy details:",
            f"  Holder:   {policy.policyholder_name}",
            f"  Active:   {active_str}",
            "  Coverages:",
            *coverage_lines,
        ]

    lines += ["", "Return your decision as JSON matching the AgentDecision schema."]
    return "\n".join(lines)


class FnolAgent:
    """Stage 1 naive FNOL adjudication agent. Satisfies the EvalAgent protocol."""

    def __init__(self) -> None:
        client: Any = build_chat_client()  # Any: MAF client type varies by provider
        self._agent: Any = client.as_agent(  # Any: MAF Agent[OptionsCoT], no stub type
            name="FnolAgent",
            instructions=INSTRUCTIONS,
        )

    async def run_scenario(self, scenario: Scenario) -> AgentRunResult:
        """Adjudicate one scenario: load data, call LLM, map result."""
        claims = load_claims()
        claim = next((c for c in claims if c.claim_number == scenario.claim_number), None)
        if claim is None:
            return AgentRunResult(
                error=f"Claim {scenario.claim_number} not found in seed data",
                reasoning="",
            )

        policies = load_policies()
        policy: Policy | None = next(
            (p for p in policies if p.policy_number == claim.policy_number), None
        )

        prompt = _render_claim_prompt(claim, policy)

        try:
            response: Any = await self._agent.run(
                prompt,
                options=OpenAIChatOptions(response_format=AgentDecision),
            )
            decision = cast(AgentDecision, response.value)
        except Exception as e:
            # Try the fence-stripping fallback before giving up
            if "Invalid JSON" in str(e) or "json_invalid" in str(e):
                try:
                    # Re-run without response_format to get raw text
                    raw = await self._agent.run(prompt)
                    cleaned = _strip_json_fences(str(raw))
                    decision = AgentDecision.model_validate_json(cleaned)
                except Exception as fallback_error:
                    return AgentRunResult(
                        tier_assigned=None,
                        decision=None,
                        payout_amount=None,
                        tool_calls_made=[],
                        reasoning="",
                        error=f"JSON parse failed; fence-strip fallback also failed: {fallback_error}",
                    )
            else:
                return AgentRunResult(error=str(e), reasoning="")

        try:
            tier_assigned: ExpectedTier | None = ExpectedTier(decision.tier)
        except ValueError:
            tier_assigned = None

        try:
            outcome_decision: ExpectedDecision | None = ExpectedDecision(decision.decision)
        except ValueError:
            outcome_decision = None

        return AgentRunResult(
            tier_assigned=tier_assigned,
            decision=outcome_decision,
            payout_amount=Decimal(str(decision.payout_amount)),
            tool_calls_made=[],
            reasoning=decision.reasoning,
            error=None,
        )


if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    from evals.scenarios import load_scenario

    async def main() -> None:
        agent = FnolAgent()
        scenario = load_scenario(Path("evals/scenarios/green-001-clean-collision.yaml"))
        result = await agent.run_scenario(scenario)
        print(f"Result: {result}")

    asyncio.run(main())
