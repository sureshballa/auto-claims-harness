"""Mock PolicyRepository backed by domain.mock_data.

Provides O(1) policy lookups over the seed dataset for use in tests,
evals, and the dev-time agent. Not for production use — the underlying
data source and the absence of any persistence layer make that clear.
"""

from __future__ import annotations

from domain.mock_data import load_policies
from domain.models import Policy


class MockDataPolicyRepository:
    """PolicyRepository implementation backed by domain.mock_data.

    Loads all policies from mock data at construction. Builds an
    internal dict keyed by policy_number for O(1) lookups. Treats
    loaded data as immutable for the lifetime of the instance.

    Satisfies the PolicyRepository Protocol structurally — does not
    declare it as a base class, since structural typing is sufficient
    and avoids the runtime cost of Protocol checking on every instance.
    """

    def __init__(self) -> None:
        """Load all policies from mock data and build the lookup index."""
        policies = load_policies()
        self._by_number: dict[str, Policy] = {
            policy.policy_number: policy for policy in policies
        }

    def get_by_number(self, policy_number: str) -> Policy | None:
        """Return the Policy with the given policy_number, or None."""
        return self._by_number.get(policy_number)
