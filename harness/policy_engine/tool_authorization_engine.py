"""ToolAuthorizationEngine — concrete PolicyEngine for tool-call gating.

Evaluates PolicyRequests whose action_name begins with "tool." against a
loaded ToolAllowlistConfig. Returns PolicyRuling(ALLOW) or PolicyRuling(DENY);
never emits ESCALATE (no human-principal approval flow in Stage 3).

Design: pure deterministic Python. No I/O, no side effects, no LLM calls.
Same PolicyRequest always produces the same PolicyRuling.
"""

from __future__ import annotations

from domain.tiers import Tier
from harness.contracts.policy import PolicyDecision, PolicyRequest, PolicyRuling
from harness.policy_engine.tool_allowlist_loader import ToolAllowlistConfig, ToolDecision

_TOOL_PREFIX = "tool."


def _to_policy_decision(td: ToolDecision) -> PolicyDecision:
    """Map ToolDecision to the corresponding PolicyDecision."""
    if td is ToolDecision.ALLOW:
        return PolicyDecision.ALLOW
    return PolicyDecision.DENY


class ToolAuthorizationEngine:
    """Concrete PolicyEngine that gates tool calls via an allowlist config.

    Satisfies harness.contracts.policy.PolicyEngine structurally — does
    not declare it as a base class (structural typing is sufficient).

    Pure deterministic Python. No I/O. Same PolicyRequest always yields
    the same PolicyRuling.

    Scope is tool actions only: action_name must start with 'tool.'.
    Non-tool actions raise ValueError — they belong to a different
    engine (not yet built).
    """

    def __init__(self, allowlist: ToolAllowlistConfig) -> None:
        self._allowlist = allowlist

    def evaluate(self, request: PolicyRequest) -> PolicyRuling:
        """Evaluate whether the requested tool call is permitted.

        Raises:
            ValueError: if action_name does not start with "tool." — this is a
                programmer error; route non-tool actions to a different engine.
        """
        # Step 1: enforce scope — only "tool.*" actions handled here.
        if not request.action_name.startswith(_TOOL_PREFIX):
            raise ValueError(
                f"ToolAuthorizationEngine handles 'tool.*' actions only; "
                f"got {request.action_name!r}. Route non-tool actions to a "
                f"different engine."
            )

        # Step 2: strip prefix to get the bare tool name used as the YAML key.
        bare_name = request.action_name[len(_TOOL_PREFIX):]

        # Step 3: look up the tool; unknown tools fall to default_decision.
        rule = self._allowlist.tools.get(bare_name)
        if rule is None:
            td = self._allowlist.default_decision
            return PolicyRuling(
                decision=_to_policy_decision(td),
                reason=(
                    f"Tool '{bare_name}' not in allowlist; "
                    f"default_decision='{td}'."
                ),
                required_escalation_to=None,
            )

        # Step 4: read and parse tier — absent or invalid tier → deny (fail closed).
        tier_raw = request.action_arguments.get("tier")
        if tier_raw is None:
            return PolicyRuling(
                decision=PolicyDecision.DENY,
                reason=(
                    f"Tool '{bare_name}' requires a 'tier' argument; "
                    f"none was provided. Denying."
                ),
                required_escalation_to=None,
            )

        try:
            tier = Tier(str(tier_raw).lower())
        except ValueError:
            valid = ", ".join(sorted(t.value for t in Tier))
            return PolicyRuling(
                decision=PolicyDecision.DENY,
                reason=(
                    f"'{tier_raw}' is not a valid tier (valid: {valid}). "
                    f"Denying tool '{bare_name}'."
                ),
                required_escalation_to=None,
            )

        # Step 5-6: apply tier-specific rule or fall through to default.
        if tier.value in rule.tier_rules:
            td = rule.tier_rules[tier.value]
            if td is ToolDecision.ALLOW:
                reason = f"Tool '{bare_name}' allowed for {tier.value}-tier claim."
            else:
                reason = f"Tool '{bare_name}' denied for {tier.value}-tier claim (tier rule)."
        else:
            td = rule.default
            if td is ToolDecision.ALLOW:
                reason = f"Tool '{bare_name}' allowed by default rule."
            else:
                reason = (
                    f"Tool '{bare_name}' denied for {tier.value}-tier claim "
                    f"(default-deny, no tier-rule match)."
                )

        return PolicyRuling(
            decision=_to_policy_decision(td),
            reason=reason,
            required_escalation_to=None,
        )
