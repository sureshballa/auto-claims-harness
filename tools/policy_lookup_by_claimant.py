"""Policy lookup by claimant tool — model-callable wrapper around PolicyRepository.find_by_claimant.

Wraps PolicyRepository.find_by_claimant() so the agent can enrich its judgment
with multi-policy context. Using a tool to find policies by claimant name lets
the model check whether a claimant is a multi-policy holder — relevant for
fraud-pattern signals or multi-policy enrichment that wouldn't be visible from
a single policy prompt alone.
"""

from __future__ import annotations

from typing import Any

from agent_framework import FunctionTool, tool

from harness.contracts import PolicyRepository


def make_policy_lookup_by_claimant(repository: PolicyRepository) -> FunctionTool:
    """Return a policy_lookup_by_claimant tool bound to the given repository via closure.

    Closure-bound repository keeps the tool decoupled from agent state and
    matches Stage 2's dependency-injection pattern — the agent passes in its
    PolicyRepository at construction time, not at call time.
    """

    @tool(
        name="policy_lookup_by_claimant",
        description=(
            "Find all policies belonging to a claimant by their full name (case-insensitive). "
            "Use this tool when you want to check whether a claimant holds multiple policies "
            "— relevant for fraud-pattern signals or multi-policy enrichment. Returns a list "
            "of matching policies, or an indicator that no policies match."
        ),
    )
    def policy_lookup_by_claimant(name: str) -> dict[str, Any]:  # Any: Pydantic model_dump
        """Retrieve all policies for a claimant. Returns found=True with list, or found=False."""
        results = repository.find_by_claimant(name)
        if not results:
            return {"found": False, "name": name, "count": 0}
        return {
            "found": True,
            "count": len(results),
            "policies": [p.model_dump(mode="json") for p in results],
        }

    return policy_lookup_by_claimant
