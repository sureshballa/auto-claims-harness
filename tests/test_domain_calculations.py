"""Tests for domain/calculations.py — coverage routing, payout math, policy activity."""

from datetime import date
from decimal import Decimal

import pytest

from domain.calculations import calculate_payout, coverage_applies, policy_active_for_claim
from domain.models import (
    Claim,
    ClaimStatus,
    Coverage,
    CoverageType,
    IncidentDetails,
    IncidentType,
    Policy,
    Vehicle,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_VEHICLE = Vehicle(
    vin="1HGCM82633A004352",
    year=2020,
    make="Honda",
    model="Accord",
    value_estimate=Decimal("18000.00"),
)

_COLLISION_COV = Coverage(
    coverage_type=CoverageType.COLLISION,
    limit=Decimal("15000.00"),
    deductible=Decimal("500.00"),
)

_COMPREHENSIVE_COV = Coverage(
    coverage_type=CoverageType.COMPREHENSIVE,
    limit=Decimal("12000.00"),
    deductible=Decimal("250.00"),
)

_LIABILITY_COV = Coverage(
    coverage_type=CoverageType.LIABILITY,
    limit=Decimal("50000.00"),
    deductible=Decimal("0.00"),
)


def _make_policy(*coverages: Coverage, effective: date, expiration: date) -> Policy:
    return Policy(
        policy_number="POL-000001",
        policyholder_name="Ada Lovelace",
        policyholder_email="ada@example.com",
        effective_date=effective,
        expiration_date=expiration,
        vehicles=[_VEHICLE],
        coverages=list(coverages),
    )


def _make_claim(incident_type: IncidentType, incident_date: date) -> Claim:
    return Claim(
        claim_number="CLM-000001",
        policy_number="POL-000001",
        vehicle_vin="1HGCM82633A004352",
        incident=IncidentDetails(
            incident_type=incident_type,
            incident_date=incident_date,
            description="Test incident.",
            location="Austin, TX",
            injuries_reported=False,
            other_parties_involved=False,
        ),
        status=ClaimStatus.OPEN,
        created_at=incident_date,
    )


_ACTIVE_POLICY = _make_policy(
    _COLLISION_COV,
    _COMPREHENSIVE_COV,
    _LIABILITY_COV,
    effective=date(2025, 1, 1),
    expiration=date(2025, 12, 31),
)

_INCIDENT_DATE = date(2025, 6, 15)


# ---------------------------------------------------------------------------
# coverage_applies
# ---------------------------------------------------------------------------


class TestCoverageApplies:
    def test_collision_returns_collision_coverage(self) -> None:
        claim = _make_claim(IncidentType.COLLISION, _INCIDENT_DATE)
        result = coverage_applies(claim, _ACTIVE_POLICY)
        assert result is not None
        assert result.coverage_type == CoverageType.COLLISION

    def test_collision_no_collision_coverage_returns_none(self) -> None:
        policy = _make_policy(
            _COMPREHENSIVE_COV,
            _LIABILITY_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, _INCIDENT_DATE)
        assert coverage_applies(claim, policy) is None

    @pytest.mark.parametrize(
        "incident_type",
        [IncidentType.THEFT, IncidentType.VANDALISM, IncidentType.WEATHER, IncidentType.FIRE],
    )
    def test_comprehensive_incident_types_return_comprehensive(
        self, incident_type: IncidentType
    ) -> None:
        claim = _make_claim(incident_type, _INCIDENT_DATE)
        result = coverage_applies(claim, _ACTIVE_POLICY)
        assert result is not None
        assert result.coverage_type == CoverageType.COMPREHENSIVE

    @pytest.mark.parametrize(
        "incident_type",
        [IncidentType.THEFT, IncidentType.VANDALISM, IncidentType.WEATHER, IncidentType.FIRE],
    )
    def test_comprehensive_incident_no_comprehensive_coverage_returns_none(
        self, incident_type: IncidentType
    ) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            _LIABILITY_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(incident_type, _INCIDENT_DATE)
        assert coverage_applies(claim, policy) is None

    def test_other_incident_always_returns_none(self) -> None:
        claim = _make_claim(IncidentType.OTHER, _INCIDENT_DATE)
        assert coverage_applies(claim, _ACTIVE_POLICY) is None

    def test_other_incident_returns_none_even_with_all_coverages(self) -> None:
        claim = _make_claim(IncidentType.OTHER, _INCIDENT_DATE)
        assert coverage_applies(claim, _ACTIVE_POLICY) is None

    def test_liability_only_policy_returns_none_for_collision(self) -> None:
        policy = _make_policy(
            _LIABILITY_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, _INCIDENT_DATE)
        assert coverage_applies(claim, policy) is None

    def test_liability_never_returned(self) -> None:
        """LIABILITY is for third-party damage; it must never be returned for own-damage claims."""
        claim = _make_claim(IncidentType.COLLISION, _INCIDENT_DATE)
        result = coverage_applies(claim, _ACTIVE_POLICY)
        assert result is None or result.coverage_type != CoverageType.LIABILITY


# ---------------------------------------------------------------------------
# calculate_payout
# ---------------------------------------------------------------------------


class TestCalculatePayout:
    def test_damage_below_deductible_returns_zero(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("300.00"), coverage) == Decimal("0")

    def test_damage_equal_to_deductible_returns_zero(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("500.00"), coverage) == Decimal("0")

    def test_damage_above_limit_returns_limit(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("25000.00"), coverage) == Decimal("10000.00")

    def test_damage_in_range_returns_damage_minus_deductible(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("3000.00"), coverage) == Decimal("2500.00")

    def test_zero_damage_returns_zero(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("0"), coverage) == Decimal("0")

    def test_zero_deductible_full_amount_up_to_limit(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COMPREHENSIVE,
            limit=Decimal("5000.00"),
            deductible=Decimal("0.00"),
        )
        assert calculate_payout(Decimal("3000.00"), coverage) == Decimal("3000.00")

    def test_negative_damage_raises_value_error(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        with pytest.raises(ValueError, match="damage_amount must be >= 0"):
            calculate_payout(Decimal("-1.00"), coverage)

    def test_damage_just_above_deductible_returns_small_payout(self) -> None:
        coverage = Coverage(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("10000.00"),
            deductible=Decimal("500.00"),
        )
        assert calculate_payout(Decimal("500.01"), coverage) == Decimal("0.01")


# ---------------------------------------------------------------------------
# policy_active_for_claim
# ---------------------------------------------------------------------------


class TestPolicyActiveForClaim:
    def test_incident_within_policy_period_returns_true(self) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, date(2025, 6, 15))
        assert policy_active_for_claim(policy, claim) is True

    def test_incident_on_effective_date_returns_true(self) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, date(2025, 1, 1))
        assert policy_active_for_claim(policy, claim) is True

    def test_incident_on_expiration_date_returns_true(self) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, date(2025, 12, 31))
        assert policy_active_for_claim(policy, claim) is True

    def test_incident_after_expiration_returns_false(self) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            effective=date(2025, 1, 1),
            expiration=date(2025, 12, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, date(2026, 1, 1))
        assert policy_active_for_claim(policy, claim) is False

    def test_incident_before_effective_date_returns_false(self) -> None:
        policy = _make_policy(
            _COLLISION_COV,
            effective=date(2025, 6, 1),
            expiration=date(2026, 5, 31),
        )
        claim = _make_claim(IncidentType.COLLISION, date(2025, 5, 31))
        assert policy_active_for_claim(policy, claim) is False
