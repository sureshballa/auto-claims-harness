"""
The business event log is the harness's audit surface.

Every business-meaningful action — claim created, claim decided, payment instructed,
escalation triggered, policy violation attempted — writes a structured event here.
This is distinct from OpenTelemetry traces, which are operational (latency, errors,
spans). The event log captures *what the system decided and why*, not *how long it took*.

The log is append-only. Once written, events are immutable. Corrections are new events
that reference the event_id of the record they supersede; the original is never modified
or deleted. This gives auditors a complete, unambiguous history.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from harness.contracts.principals import Principal


class EventKind(StrEnum):
    """Taxonomy of business events written to the audit log."""

    CLAIM_CREATED = "claim_created"
    """A new FNOL has been submitted and a claim record created."""

    CLAIM_ASSESSED = "claim_assessed"
    """The harness has completed tier classification and damage assessment for a claim."""

    CLAIM_DECIDED = "claim_decided"
    """A final approve/deny decision has been recorded for a claim."""

    CLAIM_ESCALATED = "claim_escalated"
    """A claim has been routed to a higher-tier principal because the acting principal
    lacked authority to decide it unilaterally."""

    CLAIM_APPROVED = "claim_approved"
    """An authorised principal has explicitly approved a claim following assessment
    or escalation review."""

    CLAIM_DENIED = "claim_denied"
    """An authorised principal has explicitly denied a claim following assessment
    or escalation review."""

    PAYMENT_INSTRUCTED = "payment_instructed"
    """A payment instruction has been issued for an approved claim. The instruction is
    mocked; no real money moves."""

    POLICY_VIOLATION_ATTEMPTED = "policy_violation_attempted"
    """A principal attempted an action that the policy engine denied or escalated.
    Written even when the action is ultimately blocked — the attempt itself is auditable."""

    TOOL_INVOKED = "tool_invoked"
    """An agent tool was invoked. Written before the tool executes so that crashes
    during execution are visible in the audit trail."""


class Event(BaseModel):
    """An immutable business audit record."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(description="A unique identifier for this event (ULID or UUID string).")

    event_kind: EventKind = Field(description="The type of business event this record represents.")

    timestamp: datetime = Field(
        description="Wall-clock time at which the event was recorded. Must be timezone-aware."
    )

    principal: Principal = Field(description="The actor whose action generated this event.")

    claim_number: str | None = Field(
        default=None,
        description=(
            "The claim this event is scoped to. None for events not tied to a single claim."
        ),
    )

    payload: dict[str, Any] = Field(
        description="Event-specific structured data. Schema varies by event_kind."
    )

    references: list[str] = Field(
        default_factory=list,
        description=(
            "event_ids this event references. Used when this event supersedes or "
            "corrects a prior event — the original is never modified."
        ),
    )

    @field_validator("timestamp")
    @classmethod
    def _must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("Event timestamp must be timezone-aware")
        return v


@runtime_checkable
class EventLog(Protocol):
    """Append-only business event log.

    Implementations MUST:
      - Never mutate previously-written events
      - Guarantee ordering per claim_number (per-claim total order)
      - Make every append visible to subsequent queries in the same process
    """

    def append(self, event: Event) -> None:
        """Append an event. Raises on duplicate event_id."""
        ...

    def query_by_claim(self, claim_number: str) -> list[Event]:
        """All events for a claim, in append order. Empty list if none."""
        ...

    def query_by_principal(self, principal: Principal) -> list[Event]:
        """All events where this principal acted. In append order."""
        ...

    def query_all(self) -> list[Event]:
        """All events. In append order. Intended for audit export, not hot paths."""
        ...
