"""Concrete ClaimDecisionEngine implementation for the auto-claims harness.

Composes AuthorityEngine (decision-level logic) with deterministic payout
calculation from domain.calculations (amount-level logic). The model's
proposed payout is recorded for audit but never executed; the harness
always computes the authoritative amount from first principles.
"""

from __future__ import annotations

from decimal import Decimal

from domain.calculations import calculate_payout, coverage_applies
from domain.models import Claim, Policy
from domain.tiers import TierThresholds
from evals.scenarios import ExpectedDecision
from harness.contracts.claim_decisions import ClaimDecisionRequest, ClaimDecisionRuling
from harness.policy_engine.authority import AuthorityEngine


class HarnessPolicyEngine:
    """Concrete ClaimDecisionEngine that composes authority enforcement
    with deterministic payout calculation.

    Decision logic delegates to AuthorityEngine. Payout logic uses
    domain.calculations to compute the authoritative amount; the model's
    proposed amount is recorded for audit but never paid.

    Pure deterministic Python. No I/O at evaluate() time. Same request
    always produces the same ruling.

    Satisfies the ClaimDecisionEngine Protocol structurally — does not
    declare it as a base class (structural typing is sufficient).
    """

    def __init__(
        self,
        authority_engine: AuthorityEngine,
        thresholds: TierThresholds,
    ) -> None:
        """Construct with the dependencies the engine needs at evaluate-time.

        authority_engine: handles tier-and-decision authority logic.
        thresholds: passed through to authority_engine on every evaluate().
                    Stored separately because AuthorityEngine.evaluate() takes
                    thresholds as a per-call argument (legacy signature; we
                    accept it for now and pass through).
        """
        self._authority_engine = authority_engine
        self._thresholds = thresholds

    def evaluate(self, request: ClaimDecisionRequest) -> ClaimDecisionRuling:
        """Evaluate one claim adjudication. Returns the harness's ruling.

        Steps:
        1. Run authority engine to get decision-level ruling.
        2. Compute deterministic payout from claim and policy (or 0 if
           no policy, no applicable coverage, or non-approve decision).
        3. Combine into ClaimDecisionRuling with separate audit signals
           for decision-level and amount-level overrides.
        """
        authority_ruling = self._authority_engine.evaluate(
            claim=request.claim,
            thresholds=self._thresholds,
            proposed_decision=request.proposed_decision,
            proposed_payout=request.proposed_payout,
            proposed_tier=request.proposed_tier,
        )

        deterministic_payout = self._compute_deterministic_payout(
            request.claim,
            request.policy,
        )

        if authority_ruling.final_decision == ExpectedDecision.APPROVE:
            final_payout = deterministic_payout
        else:
            final_payout = Decimal("0")

        payout_overridden = final_payout != request.proposed_payout

        reason = authority_ruling.reason
        if payout_overridden and not authority_ruling.overridden:
            reason = (
                f"{reason} Payout adjusted from model's proposed "
                f"{request.proposed_payout} to deterministic {final_payout}."
            )

        return ClaimDecisionRuling(
            proposed_decision=authority_ruling.proposed_decision,
            proposed_payout=authority_ruling.proposed_payout,
            proposed_tier=authority_ruling.proposed_tier,
            final_decision=authority_ruling.final_decision,
            final_payout=final_payout,
            computed_tier=authority_ruling.computed_tier,
            overridden=authority_ruling.overridden,
            tier_disagreement=authority_ruling.tier_disagreement,
            payout_overridden=payout_overridden,
            reason=reason,
        )

    def _compute_deterministic_payout(
        self,
        claim: Claim,
        policy: Policy | None,
    ) -> Decimal:
        """Compute the authoritative payout from claim damage and applicable coverage.

        Returns Decimal("0") in any of these cases:
          - policy is None (adversarial: claim references unknown policy)
          - claim has no damage assessment
          - no coverage from the policy applies to this incident type

        Otherwise returns calculate_payout(damage_amount, coverage), which
        already handles deductibles and limits.
        """
        if policy is None:
            return Decimal("0")
        if claim.damage is None:
            return Decimal("0")
        coverage = coverage_applies(claim, policy)
        if coverage is None:
            return Decimal("0")
        return calculate_payout(claim.damage.assessed_amount, coverage)
