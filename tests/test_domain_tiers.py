"""Tests for domain/tiers.py.

Covers TierThresholds validation, all four assign_tier outcomes,
no-damage handling, and the injury escalation rule.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.models import (
    Claim,
    ClaimStatus,
    DamageAssessment,
    IncidentDetails,
    IncidentType,
)
from domain.tiers import Tier, TierThresholds, assign_tier

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

THRESHOLDS = TierThresholds(
    green_max_damage=Decimal("2000.00"),
    yellow_max_damage=Decimal("10000.00"),
    red_max_damage=Decimal("25000.00"),
)


def _incident(*, injuries: bool = False) -> IncidentDetails:
    return IncidentDetails(
        incident_type=IncidentType.COLLISION,
        incident_date=date(2025, 3, 10),
        description="Vehicle struck a guardrail on the highway.",
        location="Dallas, TX",
        police_report_number=None,
        injuries_reported=injuries,
        other_parties_involved=False,
    )


def _claim(*, amount: Decimal | None, injuries: bool = False) -> Claim:
    damage = (
        DamageAssessment(
            assessed_amount=amount,
            assessment_source="adjuster_inspection",
            confidence=Decimal("0.90"),
        )
        if amount is not None
        else None
    )
    return Claim(
        claim_number="CLM-TEST-001",
        policy_number="POL-000001",
        vehicle_vin="1HGCM82633A123456",
        incident=_incident(injuries=injuries),
        damage=damage,
        status=ClaimStatus.OPEN,
        created_at=date(2025, 3, 10),
    )


# ---------------------------------------------------------------------------
# TierThresholds validation
# ---------------------------------------------------------------------------


def test_thresholds_valid_construction() -> None:
    t = TierThresholds(
        green_max_damage=Decimal("1000"),
        yellow_max_damage=Decimal("5000"),
        red_max_damage=Decimal("20000"),
    )
    assert t.green_max_damage < t.yellow_max_damage < t.red_max_damage


def test_thresholds_green_not_positive_raises() -> None:
    with pytest.raises(ValidationError, match="must be > 0"):
        TierThresholds(
            green_max_damage=Decimal("0"),
            yellow_max_damage=Decimal("5000"),
            red_max_damage=Decimal("20000"),
        )


def test_thresholds_yellow_not_positive_raises() -> None:
    with pytest.raises(ValidationError, match="must be > 0"):
        TierThresholds(
            green_max_damage=Decimal("1000"),
            yellow_max_damage=Decimal("-1"),
            red_max_damage=Decimal("20000"),
        )


def test_thresholds_red_not_positive_raises() -> None:
    with pytest.raises(ValidationError, match="must be > 0"):
        TierThresholds(
            green_max_damage=Decimal("1000"),
            yellow_max_damage=Decimal("5000"),
            red_max_damage=Decimal("0"),
        )


def test_thresholds_green_equals_yellow_raises() -> None:
    with pytest.raises(ValidationError, match="strictly"):
        TierThresholds(
            green_max_damage=Decimal("5000"),
            yellow_max_damage=Decimal("5000"),
            red_max_damage=Decimal("20000"),
        )


def test_thresholds_descending_order_raises() -> None:
    with pytest.raises(ValidationError, match="strictly"):
        TierThresholds(
            green_max_damage=Decimal("10000"),
            yellow_max_damage=Decimal("5000"),
            red_max_damage=Decimal("20000"),
        )


def test_thresholds_yellow_equals_red_raises() -> None:
    with pytest.raises(ValidationError, match="strictly"):
        TierThresholds(
            green_max_damage=Decimal("1000"),
            yellow_max_damage=Decimal("10000"),
            red_max_damage=Decimal("10000"),
        )


def test_thresholds_is_frozen() -> None:
    with pytest.raises(ValidationError):
        THRESHOLDS.green_max_damage = Decimal("9999")


# ---------------------------------------------------------------------------
# assign_tier — damage-based classification (no injuries)
# ---------------------------------------------------------------------------


def test_assign_tier_green_at_boundary() -> None:
    """Damage exactly at green_max_damage resolves to GREEN."""
    assert assign_tier(_claim(amount=Decimal("2000.00")), THRESHOLDS) is Tier.GREEN


def test_assign_tier_green_below_boundary() -> None:
    assert assign_tier(_claim(amount=Decimal("500.00")), THRESHOLDS) is Tier.GREEN


def test_assign_tier_yellow_just_above_green() -> None:
    assert assign_tier(_claim(amount=Decimal("2000.01")), THRESHOLDS) is Tier.YELLOW


def test_assign_tier_yellow_at_boundary() -> None:
    """Damage exactly at yellow_max_damage resolves to YELLOW."""
    assert assign_tier(_claim(amount=Decimal("10000.00")), THRESHOLDS) is Tier.YELLOW


def test_assign_tier_red_just_above_yellow() -> None:
    assert assign_tier(_claim(amount=Decimal("10000.01")), THRESHOLDS) is Tier.RED


def test_assign_tier_red_at_boundary() -> None:
    """Damage exactly at red_max_damage resolves to RED."""
    assert assign_tier(_claim(amount=Decimal("25000.00")), THRESHOLDS) is Tier.RED


def test_assign_tier_black_above_red() -> None:
    assert assign_tier(_claim(amount=Decimal("25000.01")), THRESHOLDS) is Tier.BLACK


def test_assign_tier_black_far_above_red() -> None:
    assert assign_tier(_claim(amount=Decimal("100000.00")), THRESHOLDS) is Tier.BLACK


# ---------------------------------------------------------------------------
# assign_tier — no damage assessment present
# ---------------------------------------------------------------------------


def test_assign_tier_no_damage_no_injury_is_yellow() -> None:
    """Without an assessment we can't auto-tier; YELLOW holds the claim for review."""
    assert assign_tier(_claim(amount=None), THRESHOLDS) is Tier.YELLOW


def test_assign_tier_no_damage_with_injury_is_red() -> None:
    """No assessment + injuries → YELLOW escalated to RED."""
    assert assign_tier(_claim(amount=None, injuries=True), THRESHOLDS) is Tier.RED


# ---------------------------------------------------------------------------
# assign_tier — injury escalation
# ---------------------------------------------------------------------------


def test_injury_escalates_green_to_yellow() -> None:
    """A GREEN-damage amount becomes YELLOW when injuries are reported."""
    no_injury = assign_tier(_claim(amount=Decimal("1500.00"), injuries=False), THRESHOLDS)
    with_injury = assign_tier(_claim(amount=Decimal("1500.00"), injuries=True), THRESHOLDS)
    assert no_injury is Tier.GREEN
    assert with_injury is Tier.YELLOW


def test_injury_escalates_yellow_to_red() -> None:
    assert assign_tier(_claim(amount=Decimal("5000.00"), injuries=True), THRESHOLDS) is Tier.RED


def test_injury_escalates_red_to_black() -> None:
    assert assign_tier(_claim(amount=Decimal("20000.00"), injuries=True), THRESHOLDS) is Tier.BLACK


def test_injury_does_not_escalate_black() -> None:
    """BLACK is the ceiling; injuries on a BLACK claim keep it BLACK."""
    assert assign_tier(_claim(amount=Decimal("50000.00"), injuries=True), THRESHOLDS) is Tier.BLACK
