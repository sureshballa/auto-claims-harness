"""
Protocol that the policy engine satisfies.

Middleware calls ``PolicyEngine.evaluate`` before permitting sensitive tool invocations.
The engine is a pure function on (principal, action, context): same inputs always produce
the same ruling. It never mutates state, never performs I/O, and never calls an LLM.

Keeping policy evaluation pure means it can be unit-tested exhaustively, replayed in
audits, and swapped for a different implementation without side-effect surprises.
"""

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from harness.contracts.principals import Principal, PrincipalKind


class PolicyDecision(StrEnum):
    """Outcome of a single policy evaluation."""

    ALLOW = "allow"
    """Action proceeds without further gating."""

    DENY = "deny"
    """Action is refused; the caller must handle the refusal and inform the requester."""

    ESCALATE = "escalate"
    """Action is refused pending approval from a higher-tier principal; the caller must
    surface the approval request and block until a qualifying principal grants it."""


class PolicyRuling(BaseModel):
    """The result returned by ``PolicyEngine.evaluate``."""

    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision = Field(description="The outcome of this policy evaluation.")

    reason: str = Field(
        description=(
            "A short human-readable explanation for the decision. "
            "Required for every ruling, including ALLOW, because audits need to know "
            "why an allow was granted, not just that it was."
        )
    )

    required_escalation_to: PrincipalKind | None = Field(
        default=None,
        description=(
            "For ESCALATE decisions: the minimum principal kind whose approval unblocks "
            "the action. Must be None for ALLOW and DENY decisions."
        ),
    )

    @model_validator(mode="after")
    def _escalation_consistency(self) -> "PolicyRuling":
        if self.decision is PolicyDecision.ESCALATE and self.required_escalation_to is None:
            raise ValueError("ESCALATE rulings must specify required_escalation_to")
        if self.decision is not PolicyDecision.ESCALATE and self.required_escalation_to is not None:
            raise ValueError("required_escalation_to must be None for ALLOW and DENY rulings")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        return self


class PolicyRequest(BaseModel):
    """Everything the policy engine needs to evaluate a single action."""

    model_config = ConfigDict(frozen=True)

    principal: Principal = Field(description="The actor requesting the action.")

    action_name: str = Field(
        description=(
            "A dotted identifier naming the action being requested, "
            "e.g. 'claim.approve' or 'tool.payment_instruction'. "
            "Used by policy rules to match the correct rule set."
        )
    )

    action_arguments: dict[str, Any] = Field(
        description=(
            "The arguments the action will be called with. "
            "The policy engine may inspect these — e.g., check a payment amount against "
            "a tier threshold before deciding to ALLOW or ESCALATE."
        )
    )

    claim_number: str | None = Field(
        default=None,
        description=(
            "The claim this action is scoped to, if any. "
            "None for actions that are not claim-scoped."
        ),
    )


@runtime_checkable
class PolicyEngine(Protocol):
    """Interface for the harness's policy engine.

    Implementations are pure: same request -> same ruling.
    No I/O, no mutation, no LLM calls.
    """

    def evaluate(self, request: PolicyRequest) -> PolicyRuling: ...
