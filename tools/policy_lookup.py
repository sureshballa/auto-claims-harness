"""Policy lookup tool — model-callable wrapper around PolicyRepository.

Wraps PolicyRepository.get_by_number() so the agent can verify policy details
during claim adjudication. Using a tool instead of embedding policy data in
the prompt converts a soft constraint ("read the prompt") into a hard one
("call the tool to know the answer").
"""

from __future__ import annotations

from typing import Any

from agent_framework import FunctionTool, tool

from harness.contracts import PolicyRepository


def make_policy_lookup(repository: PolicyRepository) -> FunctionTool:
    """Return a policy_lookup tool bound to the given repository via closure.

    Closure-bound repository keeps the tool decoupled from agent state and
    matches Stage 2's dependency-injection pattern — the agent passes in its
    PolicyRepository at construction time, not at call time.
    """

    @tool(
        name="policy_lookup",
        description=(
            "Look up an insurance policy by its policy number. Returns the policy "
            "details if found, or an indicator that no policy with that number exists."
        ),
    )
    def policy_lookup(policy_number: str) -> dict[str, Any]:  # Any: Pydantic model_dump return
        """Retrieve a policy record by number. Returns found=True with data, or found=False."""
        result = repository.get_by_number(policy_number)
        if result is None:
            return {"found": False, "policy_number": policy_number}
        return {"found": True, "policy": result.model_dump(mode="json")}

    return policy_lookup
