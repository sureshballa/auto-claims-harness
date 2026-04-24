"""
Principals are the harness's representation of *who is acting* at any point in a workflow.

Every agent run, every middleware invocation, and every event-log entry carries a Principal
so that actions can be attributed, audited, and policy-checked. Middleware reads the
current Principal to decide whether an operation is permitted (e.g., only SENIOR_ADJUSTER
may approve Red-tier claims). The event log writes it to every entry for immutable audit.

**Trust boundary**: Principals are set by the harness at the session boundary (authentication
layer). They are NEVER derived from, or overridden by, LLM output. A model that claims to
act as an ADJUSTER does not become one.
"""

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class PrincipalKind(StrEnum):
    """Taxonomy of actors recognised by the harness."""

    CLAIMANT = "claimant"
    """The policyholder or their representative filing a new claim."""

    ADJUSTER = "adjuster"
    """An operator authorised to review and decide Yellow-tier claims."""

    SENIOR_ADJUSTER = "senior_adjuster"
    """An operator authorised to review and decide Red-tier claims requiring elevated authority."""

    SYSTEM = "system"
    """The harness itself, acting autonomously (e.g., Green-tier auto-approvals).

    Distinct from any human actor.
    """


class Principal(BaseModel):
    """An immutable identity token carried by every harness operation."""

    model_config = ConfigDict(frozen=True)

    kind: PrincipalKind = Field(description="The role-category of this principal.")

    identifier: str = Field(
        description=(
            "A stable, unique identifier for this principal — typically an email address "
            "for human actors or the literal string 'system' for SYSTEM. "
            "MUST be stable across sessions for audit continuity."
        )
    )

    display_name: str = Field(
        description="Human-readable name used in logs and UI. Need not be unique."
    )


SYSTEM_PRINCIPAL: Final[Principal] = Principal(
    kind=PrincipalKind.SYSTEM,
    identifier="system",
    display_name="Auto Claims Harness",
)


def claimant_of(email: str, name: str) -> Principal:
    """Return a CLAIMANT principal for the given policyholder."""
    return Principal(kind=PrincipalKind.CLAIMANT, identifier=email, display_name=name)


def adjuster_of(email: str, name: str) -> Principal:
    """Return an ADJUSTER principal for the given operator."""
    return Principal(kind=PrincipalKind.ADJUSTER, identifier=email, display_name=name)


def senior_adjuster_of(email: str, name: str) -> Principal:
    """Return a SENIOR_ADJUSTER principal for the given operator."""
    return Principal(kind=PrincipalKind.SENIOR_ADJUSTER, identifier=email, display_name=name)
