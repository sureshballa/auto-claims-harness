"""Tests for harness/policy_engine/tool_authorization_engine.py."""

from __future__ import annotations

import pytest

from harness.contracts import SYSTEM_PRINCIPAL
from harness.contracts.policy import PolicyDecision, PolicyEngine, PolicyRequest
from harness.policy_engine.tool_allowlist_loader import (
    ToolAllowlistConfig,
    ToolAllowlistRule,
    ToolDecision,
)
from harness.policy_engine.tool_authorization_engine import ToolAuthorizationEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def allowlist() -> ToolAllowlistConfig:
    """In-memory allowlist mirroring the real config/tool_allowlist.yaml shape."""
    return ToolAllowlistConfig(
        default_decision=ToolDecision.DENY,
        tools={
            "policy_lookup_by_number": ToolAllowlistRule(
                default=ToolDecision.ALLOW,
                tier_rules={},
            ),
            "payment_instruction": ToolAllowlistRule(
                default=ToolDecision.DENY,
                tier_rules={"green": ToolDecision.ALLOW},
            ),
        },
    )


@pytest.fixture
def engine(allowlist: ToolAllowlistConfig) -> ToolAuthorizationEngine:
    return ToolAuthorizationEngine(allowlist)


def _req(action_name: str, tier: str | None = None) -> PolicyRequest:
    """Construct a minimal PolicyRequest. Omits 'tier' from args when None."""
    args: dict[str, str] = {}
    if tier is not None:
        args["tier"] = tier
    return PolicyRequest(
        principal=SYSTEM_PRINCIPAL,
        action_name=action_name,
        action_arguments=args,
    )


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


def test_satisfies_policy_engine_protocol_structurally(
    engine: ToolAuthorizationEngine,
) -> None:
    assert isinstance(engine, PolicyEngine)


# ---------------------------------------------------------------------------
# 2-3. Default-allow tool
# ---------------------------------------------------------------------------


def test_default_allow_tool_returns_allow(engine: ToolAuthorizationEngine) -> None:
    """policy_lookup_by_number has default=allow; any valid tier → ALLOW."""
    ruling = engine.evaluate(_req("tool.policy_lookup_by_number", tier="green"))
    assert ruling.decision == PolicyDecision.ALLOW


def test_default_allow_tool_missing_tier_returns_deny(
    engine: ToolAuthorizationEngine,
) -> None:
    """Even a default-allow tool fails closed when tier is absent."""
    ruling = engine.evaluate(_req("tool.policy_lookup_by_number"))
    assert ruling.decision == PolicyDecision.DENY


# ---------------------------------------------------------------------------
# 4-7. payment_instruction per tier
# ---------------------------------------------------------------------------


def test_payment_instruction_green_tier_returns_allow(
    engine: ToolAuthorizationEngine,
) -> None:
    ruling = engine.evaluate(_req("tool.payment_instruction", tier="green"))
    assert ruling.decision == PolicyDecision.ALLOW


def test_payment_instruction_yellow_tier_returns_deny(
    engine: ToolAuthorizationEngine,
) -> None:
    ruling = engine.evaluate(_req("tool.payment_instruction", tier="yellow"))
    assert ruling.decision == PolicyDecision.DENY


def test_payment_instruction_red_tier_returns_deny(
    engine: ToolAuthorizationEngine,
) -> None:
    ruling = engine.evaluate(_req("tool.payment_instruction", tier="red"))
    assert ruling.decision == PolicyDecision.DENY


def test_payment_instruction_black_tier_returns_deny(
    engine: ToolAuthorizationEngine,
) -> None:
    ruling = engine.evaluate(_req("tool.payment_instruction", tier="black"))
    assert ruling.decision == PolicyDecision.DENY


# ---------------------------------------------------------------------------
# 8. Unknown tool
# ---------------------------------------------------------------------------


def test_unknown_tool_returns_deny(engine: ToolAuthorizationEngine) -> None:
    """A tool not in the allowlist returns DENY naming the default_decision."""
    ruling = engine.evaluate(_req("tool.shutdown_system", tier="green"))
    assert ruling.decision == PolicyDecision.DENY
    assert "shutdown_system" in ruling.reason
    assert "default_decision" in ruling.reason


# ---------------------------------------------------------------------------
# 9. Non-tool action raises ValueError
# ---------------------------------------------------------------------------


def test_non_tool_action_raises_value_error(engine: ToolAuthorizationEngine) -> None:
    request = _req("claim.approve", tier="green")
    with pytest.raises(ValueError) as exc_info:
        engine.evaluate(request)
    assert "claim.approve" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 10. Empty bare tool name
# ---------------------------------------------------------------------------


def test_empty_bare_tool_name_returns_deny(engine: ToolAuthorizationEngine) -> None:
    """action_name='tool.' strips to '' which is not in allowlist → DENY."""
    ruling = engine.evaluate(_req("tool.", tier="green"))
    assert ruling.decision == PolicyDecision.DENY


# ---------------------------------------------------------------------------
# 11. Case-insensitive tier parsing
# ---------------------------------------------------------------------------


def test_tier_uppercase_parsed_case_insensitively(
    engine: ToolAuthorizationEngine,
) -> None:
    """Tier='GREEN' is normalised to 'green' and matched correctly."""
    lower = engine.evaluate(_req("tool.payment_instruction", tier="green"))
    upper = engine.evaluate(_req("tool.payment_instruction", tier="GREEN"))
    assert lower.decision == upper.decision == PolicyDecision.ALLOW


# ---------------------------------------------------------------------------
# 12. Invalid tier value
# ---------------------------------------------------------------------------


def test_invalid_tier_returns_deny(engine: ToolAuthorizationEngine) -> None:
    """An unrecognised tier name → DENY with reason naming the invalid value."""
    ruling = engine.evaluate(_req("tool.payment_instruction", tier="purple"))
    assert ruling.decision == PolicyDecision.DENY
    assert "purple" in ruling.reason


# ---------------------------------------------------------------------------
# 13. Tier key entirely absent from action_arguments
# ---------------------------------------------------------------------------


def test_missing_tier_in_arguments_returns_deny(
    engine: ToolAuthorizationEngine,
) -> None:
    """No 'tier' key at all → DENY with reason stating tier is required."""
    ruling = engine.evaluate(_req("tool.payment_instruction"))  # no tier kwarg
    assert ruling.decision == PolicyDecision.DENY
    assert "tier" in ruling.reason


# ---------------------------------------------------------------------------
# 14. required_escalation_to is always None
# ---------------------------------------------------------------------------


def test_required_escalation_to_is_always_none(
    engine: ToolAuthorizationEngine,
) -> None:
    """This engine never emits ESCALATE, so required_escalation_to is always None."""
    allow_ruling = engine.evaluate(_req("tool.payment_instruction", tier="green"))
    deny_ruling = engine.evaluate(_req("tool.payment_instruction", tier="yellow"))
    unknown_ruling = engine.evaluate(_req("tool.not_a_tool", tier="green"))

    assert allow_ruling.required_escalation_to is None
    assert deny_ruling.required_escalation_to is None
    assert unknown_ruling.required_escalation_to is None


# ---------------------------------------------------------------------------
# 15. Determinism
# ---------------------------------------------------------------------------


def test_evaluate_is_deterministic(engine: ToolAuthorizationEngine) -> None:
    """Same request evaluated twice returns an identical PolicyRuling."""
    request = _req("tool.payment_instruction", tier="green")
    assert engine.evaluate(request) == engine.evaluate(request)
