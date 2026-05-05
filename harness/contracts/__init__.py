"""Harness contracts — Protocol definitions and shared value types.

This package defines the interfaces every harness component must satisfy.
It is the load-bearing boundary between the harness's mechanism layer
and its policy layer. Pure Python; no MAF imports, no LLM.
"""

from harness.contracts.agent_outputs import AgentDecision
from harness.contracts.claim_decisions import (
    ClaimDecisionEngine,
    ClaimDecisionRequest,
    ClaimDecisionRuling,
)
from harness.contracts.context import ClaimAwareContextProvider
from harness.contracts.events import Event, EventKind, EventLog
from harness.contracts.policy import (
    PolicyDecision,
    PolicyEngine,
    PolicyRequest,
    PolicyRuling,
)
from harness.contracts.policy_repository import PolicyRepository
from harness.contracts.principals import (
    SYSTEM_PRINCIPAL,
    Principal,
    PrincipalKind,
    adjuster_of,
    claimant_of,
    senior_adjuster_of,
)

__all__ = [
    "SYSTEM_PRINCIPAL",
    "AgentDecision",
    "ClaimAwareContextProvider",
    "ClaimDecisionEngine",
    "ClaimDecisionRequest",
    "ClaimDecisionRuling",
    "Event",
    "EventKind",
    "EventLog",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyRepository",
    "PolicyRequest",
    "PolicyRuling",
    "Principal",
    "PrincipalKind",
    "adjuster_of",
    "claimant_of",
    "senior_adjuster_of"
]
