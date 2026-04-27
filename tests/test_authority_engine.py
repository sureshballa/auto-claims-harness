"""Tests for harness/policy_engine/authority.py.

Covers all four tiers x all three decision types, audit signals
(overridden, tier_disagreement), injury-escalation interaction,
and edge cases (negative payout, frozen ruling, determinism).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from domain.models import (
    Claim,
    ClaimStatus,
    DamageAssessment,
    IncidentDetails,
    IncidentType,
)
from domain.tiers import Tier, TierThresholds
from evals.scenarios import ExpectedDecision
from harness.policy_engine import load_permissions
from harness.policy_engine.authority import AuthorityEngine
from harness.policy_engine.permissions_loader import TierAuthorityConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TODAY = date(2024, 9, 1)
_VIN = "1HG" + "0" * 14  # valid 17-char VIN

_PERMISSIONS_PATH = Path(__file__).parent.parent / "config" / "permissions.yaml"


@pytest.fixture
def thresholds() -> TierThresholds:
    return TierThresholds(
        green_max_damage=Decimal("500"),
        yellow_max_damage=Decimal("5000"),
        red_max_damage=Decimal("25000"),
    )


@pytest.fixture
def authority_config() -> TierAuthorityConfig:
    return load_permissions(_PERMISSIONS_PATH).tier_authority


@pytest.fixture
def engine(authority_config: TierAuthorityConfig) -> AuthorityEngine:
    return AuthorityEngine(authority_config)


def make_claim_with_damage(amount: Decimal, injuries: bool = False) -> Claim:
    """Construct a minimal valid Claim with a given damage amount.

    Only damage.assessed_amount and incident.injuries_reported affect tier
    assignment; all other fields carry minimal valid values.
    """
    return Claim(
        claim_number="CLM-TEST",
        policy_number="POL-TEST",
        vehicle_vin=_VIN,
        incident=IncidentDetails(
            incident_type=IncidentType.COLLISION,
            incident_date=_TODAY,
            description="Test incident.",
            location="Test City",
            police_report_number=None,
            injuries_reported=injuries,
            other_parties_involved=False,
        ),
        damage=DamageAssessment(
            assessed_amount=amount,
            assessment_source="shop_estimate",
            confidence=Decimal("0.85"),
        ),
        status=ClaimStatus.OPEN,
        created_at=_TODAY,
        decided_at=None,
    )


# ---------------------------------------------------------------------------
# GREEN TIER — model has full authority
# ---------------------------------------------------------------------------


def test_green_approve_passes_through(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Green-tier approve proposal is accepted unchanged."""
    claim = make_claim_with_damage(Decimal("300"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("300")
    )

    assert ruling.final_decision == ExpectedDecision.APPROVE
    assert ruling.final_payout == Decimal("300")
    assert ruling.computed_tier == Tier.GREEN
    assert ruling.overridden is False


def test_green_deny_passes_through(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Green-tier deny proposal is accepted unchanged."""
    claim = make_claim_with_damage(Decimal("300"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.DENY, Decimal("0")
    )

    assert ruling.final_decision == ExpectedDecision.DENY
    assert ruling.final_payout == Decimal("0")
    assert ruling.overridden is False


def test_green_escalate_passes_through(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Green-tier escalate proposal is accepted unchanged."""
    claim = make_claim_with_damage(Decimal("300"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0")
    )

    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is False


# ---------------------------------------------------------------------------
# YELLOW TIER — only escalate allowed
# ---------------------------------------------------------------------------


def test_yellow_approve_overridden_to_escalate(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Yellow-tier approve is overridden to escalate; reason names both tier and proposal."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("2800")
    )

    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.final_payout == Decimal("0")
    assert ruling.computed_tier == Tier.YELLOW
    assert ruling.overridden is True
    assert "yellow" in ruling.reason.lower()
    assert "approve" in ruling.reason.lower()


def test_yellow_deny_overridden_to_escalate(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Yellow-tier deny is overridden to escalate; reason names both tier and proposal."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.DENY, Decimal("0")
    )

    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.final_payout == Decimal("0")
    assert ruling.overridden is True
    assert "yellow" in ruling.reason.lower()
    assert "deny" in ruling.reason.lower()


def test_yellow_escalate_accepted(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Yellow-tier escalate proposal is accepted without override."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0")
    )

    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is False


# ---------------------------------------------------------------------------
# RED TIER — only escalate allowed
# ---------------------------------------------------------------------------


def test_red_approve_overridden(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Red-tier approve is overridden to escalate."""
    claim = make_claim_with_damage(Decimal("15000"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("15000")
    )

    assert ruling.overridden is True
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.final_payout == Decimal("0")
    assert ruling.computed_tier == Tier.RED


def test_red_deny_overridden(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Red-tier deny is overridden to escalate."""
    claim = make_claim_with_damage(Decimal("15000"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.DENY, Decimal("0")
    )

    assert ruling.overridden is True
    assert ruling.final_decision == ExpectedDecision.ESCALATE


def test_red_escalate_accepted(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Red-tier escalate proposal is accepted without override."""
    claim = make_claim_with_damage(Decimal("15000"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0")
    )

    assert ruling.overridden is False
    assert ruling.computed_tier == Tier.RED


# ---------------------------------------------------------------------------
# BLACK TIER — always escalate; reason always mentions investigation
# ---------------------------------------------------------------------------


def test_black_approve_overridden(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Black-tier approve is overridden to escalate for investigation."""
    claim = make_claim_with_damage(Decimal("50000"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("50000")
    )

    assert ruling.overridden is True
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.final_payout == Decimal("0")
    assert ruling.computed_tier == Tier.BLACK
    assert "investigation" in ruling.reason.lower()


def test_black_escalate_still_routes_to_investigation(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Black-tier escalate is not an override, but investigation is still cited in reason."""
    claim = make_claim_with_damage(Decimal("50000"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0")
    )

    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is False  # model agreed; no override needed
    assert "investigation" in ruling.reason.lower()


# ---------------------------------------------------------------------------
# INJURY ESCALATION — green damage + injuries → yellow tier
# ---------------------------------------------------------------------------


def test_green_damage_with_injury_escalates_to_yellow(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """A green-damage claim with injuries is computed as yellow; approve is overridden."""
    claim = make_claim_with_damage(Decimal("300"), injuries=True)
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("300")
    )

    assert ruling.computed_tier == Tier.YELLOW
    assert ruling.final_decision == ExpectedDecision.ESCALATE
    assert ruling.overridden is True


# ---------------------------------------------------------------------------
# TIER DISAGREEMENT
# ---------------------------------------------------------------------------


def test_tier_disagreement_recorded(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Model claiming wrong tier sets tier_disagreement=True with the correct computed tier."""
    claim = make_claim_with_damage(Decimal("2800"))  # yellow
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0"),
        proposed_tier=Tier.GREEN,
    )

    assert ruling.tier_disagreement is True
    assert ruling.computed_tier == Tier.YELLOW
    assert ruling.proposed_tier == Tier.GREEN


def test_tier_agreement_recorded(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """Model claiming the correct tier sets tier_disagreement=False."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0"),
        proposed_tier=Tier.YELLOW,
    )

    assert ruling.tier_disagreement is False


def test_no_proposed_tier_means_no_disagreement(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """proposed_tier=None never triggers tier_disagreement, even on yellow claims."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.ESCALATE, Decimal("0"),
        proposed_tier=None,
    )

    assert ruling.tier_disagreement is False
    assert ruling.proposed_tier is None


# ---------------------------------------------------------------------------
# EDGE CASES
# ---------------------------------------------------------------------------


def test_negative_payout_raises_value_error(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """A negative proposed_payout is rejected before any authority logic runs."""
    claim = make_claim_with_damage(Decimal("300"))
    with pytest.raises(ValueError, match=">= 0"):
        engine.evaluate(
            claim, thresholds, ExpectedDecision.APPROVE, Decimal("-100")
        )


def test_ruling_is_frozen(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """AuthorityRuling is immutable — mutating any field raises an error."""
    claim = make_claim_with_damage(Decimal("300"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("300")
    )

    with pytest.raises(ValidationError):
        ruling.overridden = True


def test_ruling_serializable_to_dict(
    engine: AuthorityEngine, thresholds: TierThresholds
) -> None:
    """model_dump() succeeds and contains every expected key."""
    claim = make_claim_with_damage(Decimal("300"))
    ruling = engine.evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("300")
    )
    d = ruling.model_dump()

    for key in (
        "proposed_decision", "proposed_payout", "proposed_tier",
        "final_decision", "final_payout", "computed_tier",
        "overridden", "tier_disagreement", "reason",
    ):
        assert key in d, f"Missing key in model_dump(): {key!r}"


def test_engine_is_deterministic(
    authority_config: TierAuthorityConfig, thresholds: TierThresholds
) -> None:
    """Two independent AuthorityEngine instances produce identical rulings for the same inputs."""
    claim = make_claim_with_damage(Decimal("2800"))
    ruling_a = AuthorityEngine(authority_config).evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("2800"),
        proposed_tier=Tier.GREEN,
    )
    ruling_b = AuthorityEngine(authority_config).evaluate(
        claim, thresholds, ExpectedDecision.APPROVE, Decimal("2800"),
        proposed_tier=Tier.GREEN,
    )

    assert ruling_a == ruling_b
