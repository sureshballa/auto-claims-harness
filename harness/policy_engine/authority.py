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

- Authority rules are loaded from config/permissions.yaml at startup and
  injected into the engine's constructor. The engine performs no I/O.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from domain.models import Claim
from domain.tiers import Tier, TierThresholds, assign_tier
from evals.scenarios import ExpectedDecision
from harness.policy_engine.permissions_loader import TierAuthorityConfig, TierAuthorityRule


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

    Authority rules are loaded from config/permissions.yaml at startup
    and passed to the engine's constructor. The engine does not perform
    I/O at runtime.

    Reason strings are operator-facing language and remain in code (not
    externalized) — they describe what happened in human terms but do
    not constitute policy.
    """

    def __init__(self, authority_config: TierAuthorityConfig) -> None:
        self._config = authority_config

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

        rule = self._get_rule_for_tier(computed_tier)

        if proposed_decision in rule.allowed_decisions:
            final_decision = proposed_decision
            final_payout = Decimal("0") if rule.zero_payout_on_override else proposed_payout
            overridden = False
            reason = self._build_acceptance_reason(computed_tier, proposed_decision, rule)
        else:
            final_decision = rule.on_disallowed_decision
            final_payout = Decimal("0") if rule.zero_payout_on_override else proposed_payout
            overridden = True
            reason = self._build_override_reason(computed_tier, proposed_decision, rule)

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

    def _get_rule_for_tier(self, tier: Tier) -> TierAuthorityRule:
        """Return the TierAuthorityRule for the given Tier enum value."""
        if tier == Tier.GREEN:
            return self._config.green
        elif tier == Tier.YELLOW:
            return self._config.yellow
        elif tier == Tier.RED:
            return self._config.red
        elif tier == Tier.BLACK:
            return self._config.black
        else:
            # Defensive: assign_tier should never produce another value, but
            # if it ever does (e.g., new tier added), fail loud rather than
            # silently fall through.
            raise ValueError(f"No authority rule for tier {tier!r}")

    def _build_acceptance_reason(
        self, tier: Tier, decision: ExpectedDecision, rule: TierAuthorityRule
    ) -> str:
        """Construct human-readable reason when model's proposal is accepted."""
        if rule.flag_for_investigation:
            # Black tier: even accepted escalations are flagged for investigation.
            return (
                f"{tier.value.capitalize()}-tier claim: investigation required "
                f"regardless of model proposal ({decision.value}). "
                f"Routed to investigation team."
            )
        elif tier == Tier.GREEN:
            return (
                f"Green-tier claim: model's authority is full. "
                f"Final decision matches proposal ({decision.value})."
            )
        else:
            return (
                f"{tier.value.capitalize()}-tier claim: model proposed "
                f"{decision.value}, accepted."
            )

    def _build_override_reason(
        self, tier: Tier, proposed: ExpectedDecision, rule: TierAuthorityRule
    ) -> str:
        """Construct human-readable reason when model's proposal is overridden."""
        if rule.flag_for_investigation:
            return (
                f"{tier.value.capitalize()}-tier claim: investigation required "
                f"regardless of model proposal ({proposed.value}). "
                f"Routed to investigation team."
            )

        review_phrase = {
            Tier.YELLOW: "adjuster review",
            Tier.RED: "senior adjuster review",
        }.get(tier, "review")

        return (
            f"{tier.value.capitalize()}-tier claim: model proposed "
            f"{proposed.value}, but {tier.value} tier requires {review_phrase}. "
            f"Overridden to {rule.on_disallowed_decision.value}."
        )
