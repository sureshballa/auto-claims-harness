"""Tests for harness/contracts/ value types and Protocol structural conformance.

These tests verify that the contracts themselves are well-formed — not that any
particular implementation (policy engine, event log) is correct. No policy engine
exists yet; we are proving the interfaces are satisfiable.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from harness.contracts import (
    SYSTEM_PRINCIPAL,
    ClaimAwareContextProvider,
    Event,
    EventKind,
    EventLog,
    PolicyDecision,
    PolicyEngine,
    PolicyRequest,
    PolicyRuling,
    Principal,
    PrincipalKind,
    claimant_of,
)

# ---------------------------------------------------------------------------
# Principals
# ---------------------------------------------------------------------------


def test_principal_kinds_are_complete() -> None:
    assert PrincipalKind.CLAIMANT.value == "claimant"
    assert PrincipalKind.ADJUSTER.value == "adjuster"
    assert PrincipalKind.SENIOR_ADJUSTER.value == "senior_adjuster"
    assert PrincipalKind.SYSTEM.value == "system"
    assert len(PrincipalKind) == 4


def test_principal_frozen() -> None:
    p = Principal(kind=PrincipalKind.CLAIMANT, identifier="a@b.test", display_name="A")
    with pytest.raises(ValidationError):
        p.identifier = "mutated"


def test_system_principal_is_system_kind() -> None:
    assert SYSTEM_PRINCIPAL.kind is PrincipalKind.SYSTEM


def test_claimant_of_factory() -> None:
    p = claimant_of("x@y.test", "X")
    assert p.kind is PrincipalKind.CLAIMANT
    assert p.identifier == "x@y.test"
    assert p.display_name == "X"


# ---------------------------------------------------------------------------
# PolicyDecision
# ---------------------------------------------------------------------------


def test_policy_decision_members() -> None:
    assert PolicyDecision.ALLOW.value == "allow"
    assert PolicyDecision.DENY.value == "deny"
    assert PolicyDecision.ESCALATE.value == "escalate"
    assert len(PolicyDecision) == 3


# ---------------------------------------------------------------------------
# PolicyRuling validation
# ---------------------------------------------------------------------------


def test_policy_ruling_allow_requires_null_escalation() -> None:
    with pytest.raises(ValidationError):
        PolicyRuling(
            decision=PolicyDecision.ALLOW,
            reason="auto-approved",
            required_escalation_to=PrincipalKind.ADJUSTER,
        )


def test_policy_ruling_escalate_requires_escalation_target() -> None:
    with pytest.raises(ValidationError):
        PolicyRuling(
            decision=PolicyDecision.ESCALATE,
            reason="needs senior review",
            required_escalation_to=None,
        )


def test_policy_ruling_empty_reason_rejected() -> None:
    with pytest.raises(ValidationError):
        PolicyRuling(
            decision=PolicyDecision.DENY,
            reason="",
            required_escalation_to=None,
        )


# ---------------------------------------------------------------------------
# Event value type
# ---------------------------------------------------------------------------


def _valid_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = {
        "event_id": "01HX0000000000000000000000",
        "event_kind": EventKind.CLAIM_CREATED,
        "timestamp": datetime.now(UTC),
        "principal": SYSTEM_PRINCIPAL,
        "payload": {},
    }
    defaults.update(overrides)
    return Event(**defaults)


def test_event_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        _valid_event(timestamp=datetime(2024, 6, 1, 12, 0, 0))  # naive


def test_event_frozen() -> None:
    event = _valid_event()
    with pytest.raises(ValidationError):
        event.event_id = "tampered"


# ---------------------------------------------------------------------------
# Protocol structural conformance
# ---------------------------------------------------------------------------


def test_event_log_protocol_structural_conformance() -> None:
    class InMemoryEventLog:
        def __init__(self) -> None:
            self._store: list[Event] = []

        def append(self, event: Event) -> None:
            self._store.append(event)

        def query_by_claim(self, claim_number: str) -> list[Event]:
            return [e for e in self._store if e.claim_number == claim_number]

        def query_by_principal(self, principal: Principal) -> list[Event]:
            return [e for e in self._store if e.principal == principal]

        def query_all(self) -> list[Event]:
            return list(self._store)

    assert isinstance(InMemoryEventLog(), EventLog)


def test_policy_engine_protocol_structural_conformance() -> None:
    class AlwaysAllowEngine:
        def evaluate(self, request: PolicyRequest) -> PolicyRuling:
            return PolicyRuling(decision=PolicyDecision.ALLOW, reason="always allow")

    assert isinstance(AlwaysAllowEngine(), PolicyEngine)


def test_claim_aware_context_provider_protocol_structural_conformance() -> None:
    class StaticContextProvider:
        def context_for_claim(self, claim_number: str) -> str:
            return ""

    assert isinstance(StaticContextProvider(), ClaimAwareContextProvider)
