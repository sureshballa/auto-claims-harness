"""Tests for harness/policy_engine/engine.py — HarnessPolicyEngine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from domain.models import (
    Claim,
    ClaimStatus,
    Coverage,
    CoverageType,
    DamageAssessment,
    IncidentDetails,
    IncidentType,
    Policy,
    Vehicle,
)
from domain.tiers import Tier, TierThresholds
from evals.scenarios import ExpectedDecision
from harness.contracts.claim_decisions import ClaimDecisionEngine, ClaimDecisionRequest
from harness.policy_engine import AuthorityEngine, HarnessPolicyEngine, load_permissions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PERMISSIONS_PATH = Path(__file__).parent.parent / "config" / "permissions.yaml"


@pytest.fixture
def thresholds() -> TierThresholds:
    return TierThresholds(
        green_max_damage=Decimal("500"),
        yellow_max_damage=Decimal("5000"),
        red_max_damage=Decimal("25000"),
    )


@pytest.fixture
def authority_engine() -> AuthorityEngine:
    config = load_permissions(_PERMISSIONS_PATH)
    return AuthorityEngine(config.tier_authority)


@pytest.fixture
def engine(authority_engine: AuthorityEngine, thresholds: TierThresholds) -> HarnessPolicyEngine:
    return HarnessPolicyEngine(authority_engine, thresholds)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VIN = "1HGBH41JXMN109186"  # 17 chars


def make_claim_with_damage(
    damage: Decimal | None,
    incident_type: IncidentType = IncidentType.COLLISION,
) -> Claim:
    """Construct a minimal valid Claim. damage=None means no assessment yet."""
    return Claim(
        claim_number="CLM-000001",
        policy_number="POL-000001",
        vehicle_vin=_VIN,
        incident=IncidentDetails(
            incident_type=incident_type,
            incident_date=date(2026, 1, 15),
            description="Test incident",
            location="Test City, CA",
            injuries_reported=False,
            other_parties_involved=False,
        ),
        damage=DamageAssessment(
            assessed_amount=damage,
            assessment_source="adjuster_inspection",
            confidence=Decimal("0.9"),
        )
        if damage is not None
        else None,
        status=ClaimStatus.OPEN,
        created_at=date(2026, 1, 15),
    )


def make_policy_with_coverage(
    coverage_type: CoverageType,
    limit: Decimal,
    deductible: Decimal,
) -> Policy:
    """Construct a minimal valid Policy with a single coverage line."""
    return Policy(
        policy_number="POL-000001",
        policyholder_name="Test User",
        policyholder_email="test@example.com",
        effective_date=date(2025, 1, 1),
        expiration_date=date(2027, 12, 31),
        vehicles=[
            Vehicle(
                vin=_VIN,
                year=2020,
                make="Honda",
                model="Accord",
                value_estimate=Decimal("25000"),
            )
        ],
        coverages=[
            Coverage(
                coverage_type=coverage_type,
                limit=limit,
                deductible=deductible,
            )
        ],
    )


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


def test_engine_satisfies_protocol_structurally(engine: HarnessPolicyEngine) -> None:
    assert isinstance(engine, ClaimDecisionEngine)


# ---------------------------------------------------------------------------
# 2-3. Decision-side (delegation to AuthorityEngine)
# ---------------------------------------------------------------------------


def test_green_approve_passes_through(engine: HarnessPolicyEngine) -> None:
    """Green-tier approval must not be overridden."""
    claim = make_claim_with_damage(Decimal("300"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("500"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("0"),
        proposed_tier=Tier.GREEN,
    )
    ruling = engine.evaluate(request)
    assert ruling.final_decision == ExpectedDecision.APPROVE
    assert ruling.overridden is False


def test_yellow_approve_overridden_to_escalate(engine: HarnessPolicyEngine) -> None:
    """Yellow-tier claim: model's approve must be overridden to escalate."""
    claim = make_claim_with_damage(Decimal("3000"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("500"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("3000"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is True


# ---------------------------------------------------------------------------
# 4-9. Amount-side (deterministic payout)
# ---------------------------------------------------------------------------


def test_approve_uses_deterministic_payout_below_deductible(engine: HarnessPolicyEngine) -> None:
    """$300 damage against $500 deductible → harness pays $0 regardless of model proposal."""
    claim = make_claim_with_damage(Decimal("300"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("500"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("300"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_payout == Decimal("0")
    assert ruling.payout_overridden is True


def test_approve_uses_deterministic_payout_in_range(engine: HarnessPolicyEngine) -> None:
    """Model proposes wrong amount; harness substitutes calculate_payout result."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("1000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("999"),
    )
    ruling = engine.evaluate(request)
    # max(0, min(400 - 0, 1000)) == 400
    assert ruling.final_payout == Decimal("400")
    assert ruling.payout_overridden is True


def test_approve_payout_capped_at_limit(engine: HarnessPolicyEngine) -> None:
    """Payout cannot exceed the coverage limit even if damage exceeds it."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("200"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("400"),
    )
    ruling = engine.evaluate(request)
    # max(0, min(400 - 0, 200)) == 200
    assert ruling.final_payout == Decimal("200")
    assert ruling.payout_overridden is True


def test_approve_payout_zero_when_policy_is_none(engine: HarnessPolicyEngine) -> None:
    """Adversarial claim with no resolvable policy: approved decision, zero payout."""
    claim = make_claim_with_damage(Decimal("400"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=None,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("400"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_decision == ExpectedDecision.APPROVE
    assert ruling.final_payout == Decimal("0")
    assert ruling.payout_overridden is True


def test_approve_payout_zero_when_no_applicable_coverage(engine: HarnessPolicyEngine) -> None:
    """COLLISION claim against a LIABILITY-only policy: coverage_applies returns None."""
    claim = make_claim_with_damage(Decimal("400"))
    # Only LIABILITY coverage — does not apply to collision incident
    policy = make_policy_with_coverage(CoverageType.LIABILITY, Decimal("25000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("400"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_payout == Decimal("0")
    assert ruling.payout_overridden is True


def test_approve_payout_zero_when_damage_is_none(engine: HarnessPolicyEngine) -> None:
    """Claim with no damage assessment: tier defaults to YELLOW, escalated, payout=0."""
    claim = make_claim_with_damage(None)
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("1000"),
    )
    ruling = engine.evaluate(request)
    # assign_tier: damage=None → YELLOW; APPROVE not allowed → ESCALATE
    assert ruling.computed_tier == Tier.YELLOW
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.final_payout == Decimal("0")


# ---------------------------------------------------------------------------
# 10-12. Interaction (decision + amount)
# ---------------------------------------------------------------------------


def test_payout_zero_on_deny(engine: HarnessPolicyEngine) -> None:
    """Green-tier deny: authority accepts it, but engine zeroes payout regardless."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.DENY,
        proposed_payout=Decimal("100"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_decision == ExpectedDecision.DENY
    assert ruling.overridden is False
    assert ruling.final_payout == Decimal("0")
    assert ruling.payout_overridden is True


def test_payout_zero_on_escalate(engine: HarnessPolicyEngine) -> None:
    """Yellow-tier overridden to escalate: both decision and payout flags set."""
    claim = make_claim_with_damage(Decimal("3000"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("3000"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is True
    assert ruling.final_payout == Decimal("0")
    assert ruling.payout_overridden is True


def test_no_payout_override_when_amounts_match(engine: HarnessPolicyEngine) -> None:
    """Model proposes exactly the deterministic amount: payout_overridden must be False."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("1000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        # max(0, min(400 - 0, 1000)) == 400 — exact match
        proposed_payout=Decimal("400"),
    )
    ruling = engine.evaluate(request)
    assert ruling.final_payout == Decimal("400")
    assert ruling.payout_overridden is False


# ---------------------------------------------------------------------------
# 13-15. Audit fields
# ---------------------------------------------------------------------------


def test_ruling_records_proposed_values(engine: HarnessPolicyEngine) -> None:
    """The ruling must echo the request's proposal fields unchanged for audit."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("1000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("999"),
        proposed_tier=Tier.GREEN,
    )
    ruling = engine.evaluate(request)
    assert ruling.proposed_decision == request.proposed_decision
    assert ruling.proposed_payout == request.proposed_payout
    assert ruling.proposed_tier == request.proposed_tier


def test_reason_mentions_payout_adjustment_when_appropriate(engine: HarnessPolicyEngine) -> None:
    """Payout corrected without a decision override: reason must note the adjustment."""
    claim = make_claim_with_damage(Decimal("400"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("1000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("999"),
    )
    ruling = engine.evaluate(request)
    assert ruling.overridden is False
    assert ruling.payout_overridden is True
    assert "Payout adjusted" in ruling.reason


def test_reason_not_doubled_when_decision_also_overridden(engine: HarnessPolicyEngine) -> None:
    """Decision override already explains the ruling; no redundant payout-adjustment text."""
    claim = make_claim_with_damage(Decimal("3000"))
    policy = make_policy_with_coverage(CoverageType.COLLISION, Decimal("25000"), Decimal("0"))
    request = ClaimDecisionRequest(
        claim=claim,
        policy=policy,
        proposed_decision=ExpectedDecision.APPROVE,
        proposed_payout=Decimal("3000"),
    )
    ruling = engine.evaluate(request)
    assert ruling.overridden is True
    assert ruling.payout_overridden is True
    assert "Payout adjusted" not in ruling.reason
