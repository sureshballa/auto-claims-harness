"""Tests for domain/models.py.

Covers enum membership, model construction, field validation, cross-field
invariants, the Policy.is_active_on helper, and frozen immutability.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

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

# ---------------------------------------------------------------------------
# Module-level fixture constants
# ---------------------------------------------------------------------------

VALID_VIN = "1HGCM82633A123456"  # 17-char placeholder; no checksum validation yet

DEFAULT_VEHICLE = Vehicle(
    vin=VALID_VIN,
    year=2021,
    make="Honda",
    model="Accord",
    value_estimate=Decimal("18500.00"),
)

DEFAULT_COVERAGE = Coverage(
    coverage_type=CoverageType.COLLISION,
    limit=Decimal("25000.00"),
    deductible=Decimal("500.00"),
)

DEFAULT_POLICY = Policy(
    policy_number="POL-000001",
    policyholder_name="Jane Doe",
    policyholder_email="jane.doe@example.com",
    effective_date=date(2024, 1, 1),
    expiration_date=date(2025, 1, 1),
    vehicles=[DEFAULT_VEHICLE],
    coverages=[DEFAULT_COVERAGE],
)

DEFAULT_INCIDENT = IncidentDetails(
    incident_type=IncidentType.COLLISION,
    incident_date=date(2024, 6, 15),
    description="Rear-ended at a red light on Main St.",
    location="Austin, TX",
    police_report_number=None,
    injuries_reported=False,
    other_parties_involved=True,
)

DEFAULT_CLAIM = Claim(
    claim_number="CLM-000001",
    policy_number="POL-000001",
    vehicle_vin=VALID_VIN,
    incident=DEFAULT_INCIDENT,
    damage=None,
    status=ClaimStatus.OPEN,
    created_at=date(2024, 6, 15),
    decided_at=None,
)


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------


def test_coverage_type_members_and_values() -> None:
    """All three CoverageType members exist with the expected lowercase string values."""
    assert CoverageType.LIABILITY.value == "liability"
    assert CoverageType.COLLISION.value == "collision"
    assert CoverageType.COMPREHENSIVE.value == "comprehensive"
    assert set(CoverageType) == {
        CoverageType.LIABILITY,
        CoverageType.COLLISION,
        CoverageType.COMPREHENSIVE,
    }


def test_claim_status_members_and_values() -> None:
    """All six ClaimStatus members exist with the expected lowercase string values."""
    assert ClaimStatus.OPEN.value == "open"
    assert ClaimStatus.INVESTIGATING.value == "investigating"
    assert ClaimStatus.DECIDED.value == "decided"
    assert ClaimStatus.PAID.value == "paid"
    assert ClaimStatus.DENIED.value == "denied"
    assert ClaimStatus.CLOSED.value == "closed"
    assert len(ClaimStatus) == 6


def test_incident_type_members_and_values() -> None:
    """All six IncidentType members exist with the expected lowercase string values."""
    assert IncidentType.COLLISION.value == "collision"
    assert IncidentType.THEFT.value == "theft"
    assert IncidentType.VANDALISM.value == "vandalism"
    assert IncidentType.WEATHER.value == "weather"
    assert IncidentType.FIRE.value == "fire"
    assert IncidentType.OTHER.value == "other"
    assert len(IncidentType) == 6


# ---------------------------------------------------------------------------
# 2. Coverage
# ---------------------------------------------------------------------------


def test_coverage_valid_construction() -> None:
    """Coverage builds correctly with zero deductible and a positive limit."""
    cov = Coverage(
        coverage_type=CoverageType.LIABILITY,
        limit=Decimal("100000.00"),
        deductible=Decimal("0.00"),
    )
    assert cov.coverage_type is CoverageType.LIABILITY
    assert cov.limit == Decimal("100000.00")
    assert cov.deductible == Decimal("0")


def test_coverage_negative_limit_raises() -> None:
    with pytest.raises(ValidationError, match="must be >= 0"):
        Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("-1.00"),
            deductible=Decimal("500.00"),
        )


def test_coverage_negative_deductible_raises() -> None:
    with pytest.raises(ValidationError, match="must be >= 0"):
        Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("25000.00"),
            deductible=Decimal("-0.01"),
        )


# ---------------------------------------------------------------------------
# 3. Vehicle
# ---------------------------------------------------------------------------


def test_vehicle_valid_construction() -> None:
    """Vehicle builds correctly and uppercases the VIN."""
    v = Vehicle(
        vin="1hgcm82633a123456",  # lowercase input
        year=2019,
        make="Toyota",
        model="Camry",
        value_estimate=Decimal("14000.00"),
    )
    assert v.vin == "1HGCM82633A123456"
    assert v.year == 2019


def test_vehicle_vin_too_short_raises() -> None:
    with pytest.raises(ValidationError, match="17 characters"):
        Vehicle(
            vin="1HGCM82633A12345",  # 16 chars
            year=2020,
            make="Honda",
            model="Civic",
            value_estimate=Decimal("12000.00"),
        )


def test_vehicle_vin_too_long_raises() -> None:
    with pytest.raises(ValidationError, match="17 characters"):
        Vehicle(
            vin="1HGCM82633A12345678",  # 19 chars
            year=2020,
            make="Honda",
            model="Civic",
            value_estimate=Decimal("12000.00"),
        )


def test_vehicle_year_too_old_raises() -> None:
    with pytest.raises(ValidationError, match="year must be between"):
        Vehicle(
            vin=VALID_VIN,
            year=1899,
            make="Ford",
            model="Model T",
            value_estimate=Decimal("50000.00"),
        )


def test_vehicle_year_too_far_future_raises() -> None:
    future_year = date.today().year + 2
    with pytest.raises(ValidationError, match="year must be between"):
        Vehicle(
            vin=VALID_VIN,
            year=future_year,
            make="Honda",
            model="Accord",
            value_estimate=Decimal("30000.00"),
        )


# ---------------------------------------------------------------------------
# 4. Policy
# ---------------------------------------------------------------------------


def test_policy_valid_construction() -> None:
    """Policy accepts one vehicle and one coverage without error."""
    assert DEFAULT_POLICY.policy_number == "POL-000001"
    assert len(DEFAULT_POLICY.vehicles) == 1
    assert len(DEFAULT_POLICY.coverages) == 1


def test_policy_empty_vehicles_raises() -> None:
    with pytest.raises(ValidationError, match="at least one vehicle"):
        Policy(
            policy_number="POL-000002",
            policyholder_name="John Smith",
            policyholder_email="john.smith@example.com",
            effective_date=date(2024, 1, 1),
            expiration_date=date(2025, 1, 1),
            vehicles=[],
            coverages=[DEFAULT_COVERAGE],
        )


def test_policy_empty_coverages_raises() -> None:
    with pytest.raises(ValidationError, match="at least one coverage"):
        Policy(
            policy_number="POL-000003",
            policyholder_name="John Smith",
            policyholder_email="john.smith@example.com",
            effective_date=date(2024, 1, 1),
            expiration_date=date(2025, 1, 1),
            vehicles=[DEFAULT_VEHICLE],
            coverages=[],
        )


def test_policy_duplicate_coverage_type_raises() -> None:
    second_collision = Coverage(
        coverage_type=CoverageType.COLLISION,
        limit=Decimal("30000.00"),
        deductible=Decimal("1000.00"),
    )
    with pytest.raises(ValidationError, match="duplicate coverage type"):
        Policy(
            policy_number="POL-000004",
            policyholder_name="John Smith",
            policyholder_email="john.smith@example.com",
            effective_date=date(2024, 1, 1),
            expiration_date=date(2025, 1, 1),
            vehicles=[DEFAULT_VEHICLE],
            coverages=[DEFAULT_COVERAGE, second_collision],
        )


def test_policy_is_active_on_inside_period() -> None:
    """A date strictly inside the effective-to-expiration window returns True."""
    assert DEFAULT_POLICY.is_active_on(date(2024, 6, 15)) is True


def test_policy_is_active_on_effective_date_boundary() -> None:
    """The effective_date itself is included in coverage."""
    assert DEFAULT_POLICY.is_active_on(date(2024, 1, 1)) is True


def test_policy_is_active_on_expiration_date_boundary() -> None:
    """The expiration_date itself is included in coverage."""
    assert DEFAULT_POLICY.is_active_on(date(2025, 1, 1)) is True


def test_policy_is_active_on_before_period() -> None:
    assert DEFAULT_POLICY.is_active_on(date(2023, 12, 31)) is False


def test_policy_is_active_on_after_period() -> None:
    assert DEFAULT_POLICY.is_active_on(date(2025, 1, 2)) is False


# ---------------------------------------------------------------------------
# 5. Claim
# ---------------------------------------------------------------------------


def test_claim_valid_construction_no_damage() -> None:
    """Claim builds correctly with damage=None (pre-assessment state)."""
    assert DEFAULT_CLAIM.claim_number == "CLM-000001"
    assert DEFAULT_CLAIM.damage is None
    assert DEFAULT_CLAIM.status is ClaimStatus.OPEN
    assert DEFAULT_CLAIM.decided_at is None


def test_claim_valid_construction_with_damage() -> None:
    """Claim builds correctly once a DamageAssessment has been attached."""
    assessment = DamageAssessment(
        assessed_amount=Decimal("4750.00"),
        assessment_source="shop_estimate",
        confidence=Decimal("0.85"),
    )
    claim = Claim(
        claim_number="CLM-000002",
        policy_number="POL-000001",
        vehicle_vin=VALID_VIN,
        incident=DEFAULT_INCIDENT,
        damage=assessment,
        status=ClaimStatus.INVESTIGATING,
        created_at=date(2024, 6, 15),
        decided_at=None,
    )
    assert claim.damage is not None
    assert claim.damage.assessed_amount == Decimal("4750.00")
    assert claim.damage.confidence == Decimal("0.85")


def test_claim_any_status_is_constructable() -> None:
    """Status transitions are not enforced at construction time; all values are valid."""
    for status in ClaimStatus:
        claim = Claim(
            claim_number="CLM-000099",
            policy_number="POL-000001",
            vehicle_vin=VALID_VIN,
            incident=DEFAULT_INCIDENT,
            status=status,
            created_at=date(2024, 6, 15),
        )
        assert claim.status is status


# ---------------------------------------------------------------------------
# 6. Frozen immutability
# ---------------------------------------------------------------------------


def test_coverage_is_frozen() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_COVERAGE.limit = Decimal("99999.00")


def test_vehicle_is_frozen() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_VEHICLE.year = 1999


def test_policy_is_frozen() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_POLICY.policy_number = "POL-HACKED"


def test_claim_is_frozen() -> None:
    with pytest.raises(ValidationError):
        DEFAULT_CLAIM.status = ClaimStatus.CLOSED
