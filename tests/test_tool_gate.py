"""Tests for harness/middleware/tool_gate.py.

Tests the gate wrapper behavior in isolation — uses a StubEngine that
returns scripted rulings rather than exercising ToolAuthorizationEngine.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from agent_framework import tool

from domain.tiers import Tier
from harness.contracts import SYSTEM_PRINCIPAL
from harness.contracts.policy import PolicyDecision, PolicyRequest, PolicyRuling
from harness.contracts.principals import PrincipalKind
from harness.middleware.tool_gate import gated_tool

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class StubEngine:
    """Returns rulings in FIFO order; records every PolicyRequest it receives."""

    def __init__(self, rulings: list[PolicyRuling]) -> None:
        self._rulings = list(rulings)
        self.calls: list[PolicyRequest] = []

    def evaluate(self, request: PolicyRequest) -> PolicyRuling:
        self.calls.append(request)
        return self._rulings.pop(0)


def _allow(reason: str = "stub: allow") -> PolicyRuling:
    return PolicyRuling(decision=PolicyDecision.ALLOW, reason=reason)


def _deny(reason: str = "stub: deny") -> PolicyRuling:
    return PolicyRuling(decision=PolicyDecision.DENY, reason=reason)


def _escalate(reason: str = "stub: escalate") -> PolicyRuling:
    return PolicyRuling(
        decision=PolicyDecision.ESCALATE,
        reason=reason,
        required_escalation_to=PrincipalKind.ADJUSTER,
    )


def _green() -> Tier:
    return Tier.GREEN


# ---------------------------------------------------------------------------
# Inner tool fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def inner_add():  # type: ignore[no-untyped-def]
    """A simple FunctionTool for use in gate tests."""

    @tool(name="add", description="Add two integers.")
    def add(a: int, b: int) -> int:
        return a + b

    return add


# ---------------------------------------------------------------------------
# 1. Metadata preservation
# ---------------------------------------------------------------------------


def test_wrapper_preserves_name_description_schema(inner_add: Any) -> None:
    engine = StubEngine([_allow()])
    outer = gated_tool(inner_add, engine, _green)

    assert outer.name == inner_add.name
    assert outer.description == inner_add.description
    assert outer.to_json_schema_spec() == inner_add.to_json_schema_spec()


# ---------------------------------------------------------------------------
# 2. ALLOW path — inner called, result returned
# ---------------------------------------------------------------------------


def test_allow_invokes_inner_and_returns_result(inner_add: Any) -> None:
    engine = StubEngine([_allow()])
    outer = gated_tool(inner_add, engine, _green)

    result_outer = asyncio.run(outer.invoke(arguments={"a": 3, "b": 4}))
    result_inner = asyncio.run(inner_add.invoke(arguments={"a": 3, "b": 4}))

    # Both return list[Content]; compare the text payload.
    assert result_outer[0].text == result_inner[0].text
    assert len(engine.calls) == 1  # engine was consulted


# ---------------------------------------------------------------------------
# 3. DENY path — inner NOT called, denial JSON returned
# ---------------------------------------------------------------------------


def test_deny_does_not_invoke_inner_and_returns_denial(inner_add: Any) -> None:
    call_count = 0

    @tool(name="add", description="Add two integers.")
    def add_counted(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        return a + b

    engine = StubEngine([_deny("test denial reason")])
    outer = gated_tool(add_counted, engine, _green)

    result = asyncio.run(outer.invoke(arguments={"a": 1, "b": 2}))

    assert call_count == 0
    text = result[0].text
    assert text is not None
    payload = json.loads(text)
    assert payload["denied"] is True
    assert payload["tool"] == "add"
    assert "test denial reason" in payload["reason"]


# ---------------------------------------------------------------------------
# 4. ESCALATE treated identically to DENY
# ---------------------------------------------------------------------------


def test_escalate_treated_as_deny(inner_add: Any) -> None:
    call_count = 0

    @tool(name="add", description="Add two integers.")
    def add_counted2(a: int, b: int) -> int:
        nonlocal call_count
        call_count += 1
        return a + b

    engine = StubEngine([_escalate()])
    outer = gated_tool(add_counted2, engine, _green)

    result = asyncio.run(outer.invoke(arguments={"a": 1, "b": 2}))

    assert call_count == 0
    text = result[0].text
    assert text is not None
    payload = json.loads(text)
    assert payload["denied"] is True


# ---------------------------------------------------------------------------
# 5. PolicyRequest fields
# ---------------------------------------------------------------------------


def test_policy_request_has_correct_fields(inner_add: Any) -> None:
    engine = StubEngine([_allow()])
    outer = gated_tool(inner_add, engine, _green)

    asyncio.run(outer.invoke(arguments={"a": 1, "b": 2}))

    req = engine.calls[0]
    assert req.principal == SYSTEM_PRINCIPAL
    assert req.action_name == "tool.add"
    assert req.action_arguments["tier"] == Tier.GREEN.value
    assert req.action_arguments["a"] == 1
    assert req.action_arguments["b"] == 2


# ---------------------------------------------------------------------------
# 6. tier_provider called fresh on every invoke
# ---------------------------------------------------------------------------


def test_tier_provider_called_fresh_per_invocation(inner_add: Any) -> None:
    tiers = [Tier.GREEN, Tier.YELLOW, Tier.RED]
    idx = 0

    def rotating_tier() -> Tier:
        nonlocal idx
        t = tiers[idx % len(tiers)]
        idx += 1
        return t

    engine = StubEngine([_allow(), _allow(), _allow()])
    outer = gated_tool(inner_add, engine, rotating_tier)

    asyncio.run(outer.invoke(arguments={"a": 1, "b": 1}))
    asyncio.run(outer.invoke(arguments={"a": 1, "b": 1}))
    asyncio.run(outer.invoke(arguments={"a": 1, "b": 1}))

    tiers_seen = [c.action_arguments["tier"] for c in engine.calls]
    assert tiers_seen == [Tier.GREEN.value, Tier.YELLOW.value, Tier.RED.value]


# ---------------------------------------------------------------------------
# 7. claim_number propagated when present; None when absent
# ---------------------------------------------------------------------------


def test_claim_number_propagated_when_present() -> None:
    @tool(name="pay", description="Issue payment.")
    def pay(claim_number: str, amount: float) -> str:
        return "ok"

    engine = StubEngine([_allow()])
    outer = gated_tool(pay, engine, _green)

    asyncio.run(outer.invoke(arguments={"claim_number": "CLM-001", "amount": 100.0}))

    req = engine.calls[0]
    assert req.claim_number == "CLM-001"


def test_claim_number_is_none_when_absent(inner_add: Any) -> None:
    engine = StubEngine([_allow()])
    outer = gated_tool(inner_add, engine, _green)

    asyncio.run(outer.invoke(arguments={"a": 1, "b": 2}))

    assert engine.calls[0].claim_number is None


# ---------------------------------------------------------------------------
# 8. kwargs forwarded to inner do NOT include injected "tier"
# ---------------------------------------------------------------------------


def test_inner_does_not_receive_injected_tier() -> None:
    received: dict[str, Any] = {}

    @tool(name="add", description="Add two integers.")
    def add_recorder(a: int, b: int) -> int:
        received["a"] = a
        received["b"] = b
        received["has_tier"] = "tier" in received
        return a + b

    engine = StubEngine([_allow()])
    outer = gated_tool(add_recorder, engine, _green)

    asyncio.run(outer.invoke(arguments={"a": 5, "b": 6}))

    assert received["a"] == 5
    assert received["b"] == 6
    # "tier" was injected into engine_args only, never into the kwargs
    # forwarded to inner.invoke(), so the function never sees it.
    assert "tier" not in received
