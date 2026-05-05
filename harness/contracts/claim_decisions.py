"""Contract for the harness's claim adjudication authority layer.

Defines ClaimDecisionEngine, the Protocol that any claim-adjudication
implementation must satisfy. This is distinct from PolicyEngine
(harness/contracts/policy.py), which governs tool-call authorization.
Both contracts exist and serve different purposes:

  PolicyEngine       — Should a principal be allowed to invoke this tool?
                       (Stage 3, per-tool authorization)
  ClaimDecisionEngine — Given the model's proposed verdict on a claim,
                        what is the harness's authoritative ruling?
                        (Stage 2, authority enforcement)

Implementations are pure functions on their inputs: same request always
produces the same ruling. They do not perform I/O, do not call LLMs,
and do not mutate state. This makes them exhaustively testable, safely
replayable in audits, and swappable without side-effect surprises.

The principle enforced here: "the model proposes; the harness answers."
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from domain.models import Claim, Policy
from domain.tiers import Tier
from evals.scenarios import ExpectedDecision


class ClaimDecisionRequest(BaseModel):
    """Everything the ClaimDecisionEngine needs to adjudicate one claim.

    The model's proposal (decision, payout, tier) is recorded as input;
    the harness computes its authoritative response in the ruling.
    """

    model_config = ConfigDict(frozen=True)

    claim: Claim = Field(
        description="The claim being adjudicated.",
    )
    policy: Policy | None = Field(
        description=(
            "The policy against which this claim is filed. None for "
            "adversarial cases where the policy could not be resolved "
            "(e.g., claim references a non-existent policy number)."
        ),
    )
    proposed_decision: ExpectedDecision = Field(
        description="The decision the model proposed.",
    )
    proposed_payout: Decimal = Field(
        description=(
            "The payout the model proposed (USD, non-negative). "
            "Recorded for audit; the harness may compute and substitute "
            "its own deterministic amount."
        ),
    )
    proposed_tier: Tier | None = Field(
        default=None,
        description=(
            "The tier the model claimed, if any. Echoed for audit only; "
            "the engine computes the authoritative tier itself."
        ),
    )


class ClaimDecisionRuling(BaseModel):
    """The harness's authoritative response to a claim adjudication request.

    Records both the model's proposal and the harness's final decision so
    audits can reconstruct exactly what was proposed, what was allowed,
    and where they differed.

    Two independent override flags allow audits to distinguish between
    decision-level changes (overridden) and amount-level changes
    (payout_overridden) — they often co-occur but are separately meaningful.
    """

    model_config = ConfigDict(frozen=True)

    # Echo of the model's proposal (for audit)
    proposed_decision: ExpectedDecision = Field(
        description="The decision the model proposed.",
    )
    proposed_payout: Decimal = Field(
        description="The payout the model proposed (USD, non-negative).",
    )
    proposed_tier: Tier | None = Field(
        description="The tier the model claimed, or None if not provided.",
    )

    # Harness-authoritative outcome
    final_decision: ExpectedDecision = Field(
        description="The decision the harness allows. May equal proposal or override it.",
    )
    final_payout: Decimal = Field(
        description=(
            "The payout the harness will execute (USD, non-negative). "
            "May differ from proposed_payout if the harness computed its "
            "own amount or zeroed it on override."
        ),
    )
    computed_tier: Tier = Field(
        description="The tier computed by the harness from the claim's actual data.",
    )

    # Audit signals
    overridden: bool = Field(
        description="True if final_decision differs from proposed_decision.",
    )
    tier_disagreement: bool = Field(
        description="True if proposed_tier is set and differs from computed_tier.",
    )
    payout_overridden: bool = Field(
        description=(
            "True if final_payout differs from proposed_payout. Set independently "
            "of `overridden` so audits can see decision-level vs amount-level changes."
        ),
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable explanation of why the ruling came out this way.",
    )


@runtime_checkable
class ClaimDecisionEngine(Protocol):
    """Protocol for the harness's claim adjudication authority layer.

    Implementations are pure functions on their inputs: same request
    always produces the same ruling. They do not perform I/O, do not
    call LLMs, and do not mutate state.

    Implementations enforce the principle "the model proposes; the
    harness answers." The model's proposal is recorded for audit; the
    final decision is the harness's call.
    """

    def evaluate(self, request: ClaimDecisionRequest) -> ClaimDecisionRuling: ...
