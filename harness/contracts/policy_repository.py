"""Contract for the harness's policy retrieval layer.

Abstracts how the harness obtains a Policy given a policy_number. Concrete
implementations are swapped in by callers at construction time, keeping the
harness independent of the underlying storage mechanism:

  JsonFilePolicyRepository  — loads from mock JSON files (Stage 1/2 dev)
  DatabasePolicyRepository  — queries a relational store (production)
  ExternalApiPolicyRepository — calls an insurance policy API (future)

The harness depends only on this Protocol; it never imports a concrete
implementation directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from domain.models import Policy


@runtime_checkable
class PolicyRepository(Protocol):
    """Read-only interface for retrieving policies by policy_number.

    Implementations are typically constructed once at startup and
    reused for the process lifetime. Implementations should treat
    loaded policy data as immutable — the harness assumes that two
    calls with the same policy_number return equivalent data.

    Returns None when the policy_number does not exist. This is a
    first-class outcome, not an exception, because adversarial cases
    (claims referencing non-existent policies) are part of normal
    operation.
    """

    def get_by_number(self, policy_number: str) -> Policy | None:
        """Return the Policy with the given policy_number, or None if no such policy exists.

        Args:
            policy_number: The insurer-assigned policy identifier
                (e.g., "POL-000123").

        Returns:
            The matching Policy, or None if the policy_number is unknown.
        """
        ...
