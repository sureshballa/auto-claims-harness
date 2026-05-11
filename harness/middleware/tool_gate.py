"""Tool-call gate — wraps a FunctionTool with PolicyEngine authorization.

Embodies "model proposes, harness gates": the model decides to call a tool,
but the harness checks whether the current claim's tier permits that call
before forwarding to the actual implementation. The gate is transparent to
MAF — the outer FunctionTool is indistinguishable from the inner one at
the schema level.

This is the production form of the pattern proven in scripts/spike_gated_tool.py.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from agent_framework import FunctionTool

from domain.tiers import Tier
from harness.contracts.policy import PolicyDecision, PolicyEngine, PolicyRequest
from harness.contracts.principals import SYSTEM_PRINCIPAL


def gated_tool(
    inner: FunctionTool,
    engine: PolicyEngine,
    tier_provider: Callable[[], Tier],
) -> FunctionTool:
    """Wrap a FunctionTool with a PolicyEngine gate keyed on the current claim tier.

    Returns a new FunctionTool with the same name, description, and input_model
    as `inner`. When the returned tool is invoked by MAF:

    1. Calls `tier_provider()` to obtain the harness-computed tier for the
       current scenario. This is always the harness's independent calculation —
       never the tier the model claimed.

    2. Builds a PolicyRequest with `action_name = "tool." + inner.name` and
       injects the tier into `action_arguments` alongside the tool's own kwargs.
       The tier key is for the engine only; the inner tool never sees it.

    3. Calls `engine.evaluate(request)`. On ALLOW, delegates to `inner.invoke()`.
       On DENY or ESCALATE, returns a JSON denial payload without calling inner.

    Args:
        inner: The FunctionTool to gate. Its name, description, and input_model
            are preserved verbatim on the returned tool.
        engine: PolicyEngine that decides allow/deny. Called on every invocation.
        tier_provider: Zero-argument callable returning the current Tier. Called
            fresh at invocation time — never cached — so the tier tracks the
            scenario being evaluated, not the agent's lifetime.

    Returns:
        A FunctionTool that is schema-identical to `inner` but guarded by the engine.
    """

    async def _wrapper(**kwargs: Any) -> Any:  # Any: MAF passes/receives tool args as Any
        tier = tier_provider()

        # Build engine args with injected tier — separate dict, never mutate kwargs.
        engine_args: dict[str, Any] = {**kwargs, "tier": tier.value}
        raw_cn: Any = kwargs.get("claim_number")
        claim_number: str | None = raw_cn if isinstance(raw_cn, str) else None

        request = PolicyRequest(
            principal=SYSTEM_PRINCIPAL,
            action_name=f"tool.{inner.name}",
            action_arguments=engine_args,
            claim_number=claim_number,
        )
        ruling = engine.evaluate(request)

        if ruling.decision is PolicyDecision.ALLOW:
            return await inner.invoke(arguments=kwargs)

        return json.dumps({
            "denied": True,
            "tool": inner.name,
            "reason": ruling.reason,
        })

    return FunctionTool(
        name=inner.name,
        description=inner.description,
        func=_wrapper,
        input_model=inner.input_model,
    )
