"""Authority engine — the harness's authoritative decision layer.

Enforces the principle "the model proposes; the harness answers." Given a
model's proposed decision and the claim it applies to, the engine returns
an AuthorityRuling: the harness's final word on what actually happens.

Design notes:

- The engine computes the tier ITSELF from the claim and thresholds. The
  model's claimed tier is echoed in the ruling for audit purposes but is
  never trusted for routing. This was motivated by an observed failure:
  yellow-001 model reported tier=green for a claim that scored yellow.

- The engine is pure deterministic Python: no LLM, no MAF, no I/O.
  Same inputs always produce the same ruling. Fully testable in isolation.

- Authority rules are hard-coded in this stage. Externalization to
  config/permissions.yaml is planned for Lesson 2.3.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from domain.models import Claim
from domain.tiers import Tier, TierThresholds, assign_tier
from evals.scenarios import ExpectedDecision


class AuthorityRuling(BaseModel):
    """A ruling from the AuthorityEngine.

    Records both what the model proposed and what the harness actually
    decided, so audits can reconstruct whether the model exceeded its
    authority and how the override was applied.
    """

    model_config = ConfigDict(frozen=True)

    # Proposal echoed from the model (for audit)
    proposed_decision: ExpectedDecision = Field(
        description="The decision the model proposed."
    )
    proposed_payout: Decimal = Field(
        description="The payout the model proposed. Always non-negative."
    )
    proposed_tier: Tier | None = Field(
        description="The tier the model claimed, if any. None if model didn't say."
    )

    # Harness-authoritative outcome
    final_decision: ExpectedDecision = Field(
        description="The decision the harness allows. May equal proposed_decision or override it."
    )
    final_payout: Decimal = Field(
        description="The payout the harness will execute. Always non-negative."
    )
    computed_tier: Tier = Field(
        description="The tier computed by the harness from the claim's actual data."
    )

    # Audit signals
    overridden: bool = Field(
        description="True if the harness's final decision differs from the model's proposal."
    )
    tier_disagreement: bool = Field(
        description="True if the model's claimed tier differs from the computed tier."
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable explanation of why the ruling came out this way.",
    )


class AuthorityEngine:
    """Pure deterministic authority engine. Same inputs → same ruling.

    Hard-coded rules at this stage; will be externalized to
    config/permissions.yaml in Lesson 2.3.
    """

    def evaluate(
        self,
        claim: Claim,
        thresholds: TierThresholds,
        proposed_decision: ExpectedDecision,
        proposed_payout: Decimal,
        proposed_tier: Tier | None = None,
    ) -> AuthorityRuling:
        """Apply the harness's authority rules to the model's proposal.

        The tier is computed independently from the claim; the model's
        claimed tier is echoed for audit but never used for routing.

        Args:
            claim: The actual claim being adjudicated.
            thresholds: Tier thresholds (loaded from config).
            proposed_decision: What the model said to do.
            proposed_payout: What the model proposed to pay (must be >= 0).
            proposed_tier: What the model claimed the tier was.
                None if the model did not report a tier.

        Returns:
            AuthorityRuling with both proposal and final decision recorded.

        Raises:
            ValueError: if proposed_payout is negative.
        """
        if proposed_payout < Decimal("0"):
            raise ValueError(
                f"proposed_payout must be >= 0, got {proposed_payout}"
            )

        computed_tier = assign_tier(claim, thresholds)
        tier_disagreement = (
            proposed_tier is not None and proposed_tier != computed_tier
        )

        final_decision: ExpectedDecision
        final_payout: Decimal
        overridden: bool
        reason: str

        if computed_tier == Tier.GREEN:
            final_decision = proposed_decision
            final_payout = proposed_payout
            overridden = False
            reason = (
                f"Green-tier claim: model's authority is full. "
                f"Final decision matches proposal ({proposed_decision.value})."
            )

        elif computed_tier == Tier.YELLOW:
            if proposed_decision == ExpectedDecision.ESCALATE:
                final_decision = ExpectedDecision.ESCALATE
                final_payout = Decimal("0")
                overridden = False
                reason = "Yellow-tier claim: model proposed escalate, accepted."
            else:
                final_decision = ExpectedDecision.ESCALATE
                final_payout = Decimal("0")
                overridden = True
                reason = (
                    f"Yellow-tier claim: model proposed {proposed_decision.value}, "
                    f"but yellow tier requires adjuster review. Overridden to escalate."
                )

        elif computed_tier == Tier.RED:
            if proposed_decision == ExpectedDecision.ESCALATE:
                final_decision = ExpectedDecision.ESCALATE
                final_payout = Decimal("0")
                overridden = False
                reason = "Red-tier claim: model proposed escalate, accepted."
            else:
                final_decision = ExpectedDecision.ESCALATE
                final_payout = Decimal("0")
                overridden = True
                reason = (
                    f"Red-tier claim: model proposed {proposed_decision.value}, "
                    f"but red tier requires senior adjuster review. Overridden to escalate."
                )

        else:  # Tier.BLACK
            final_decision = ExpectedDecision.ESCALATE
            final_payout = Decimal("0")
            overridden = proposed_decision != ExpectedDecision.ESCALATE
            reason = (
                f"Black-tier claim: investigation required regardless of model proposal "
                f"({proposed_decision.value}). Routed to investigation team."
            )

        return AuthorityRuling(
            proposed_decision=proposed_decision,
            proposed_payout=proposed_payout,
            proposed_tier=proposed_tier,
            final_decision=final_decision,
            final_payout=final_payout,
            computed_tier=computed_tier,
            overridden=overridden,
            tier_disagreement=tier_disagreement,
            reason=reason,
        )
