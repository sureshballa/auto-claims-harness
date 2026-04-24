"""Tests for domain/mock_data — seed data integrity and end-to-end tier coverage."""

from collections import Counter
from decimal import Decimal

import pytest

from domain.mock_data import load_claims, load_policies
from domain.models import Claim, CoverageType, IncidentType, Policy
from domain.tiers import Tier, TierThresholds, assign_tier

# Design-intent thresholds for the seed data:
#   green 100-450, yellow 800-4500, red 8000-20000, black 35000+
# Move to config/ once the YAML loader is wired in Stage 1.
_THRESHOLDS = TierThresholds(
    green_max_damage=Decimal("500"),
    yellow_max_damage=Decimal("5000"),
    red_max_damage=Decimal("25000"),
)


@pytest.fixture(scope="module")
def policies() -> list[Policy]:
    """All 50 seed policies, loaded once per test session."""
    return load_policies()


@pytest.fixture(scope="module")
def claims() -> list[Claim]:
    """All 20 seed claims, loaded once per test session."""
    return load_claims()


# ---------------------------------------------------------------------------
# Basic cardinality
# ---------------------------------------------------------------------------


def test_load_policies_returns_50(policies: list[Policy]) -> None:
    assert len(policies) == 50


def test_load_claims_returns_20(claims: list[Claim]) -> None:
    assert len(claims) == 20


# ---------------------------------------------------------------------------
# Uniqueness
# ---------------------------------------------------------------------------


def test_all_policies_have_unique_numbers(policies: list[Policy]) -> None:
    assert len({p.policy_number for p in policies}) == 50


def test_all_claims_have_unique_numbers(claims: list[Claim]) -> None:
    assert len({c.claim_number for c in claims}) == 20


# ---------------------------------------------------------------------------
# Coverage invariants
# ---------------------------------------------------------------------------


def test_all_policies_have_at_least_liability(policies: list[Policy]) -> None:
    for p in policies:
        types = {c.coverage_type for c in p.coverages}
        assert CoverageType.LIABILITY in types, f"{p.policy_number} is missing LIABILITY coverage"


# ---------------------------------------------------------------------------
# Valid-claim referential integrity
# ---------------------------------------------------------------------------


def test_all_claim_vehicles_exist_in_some_policy_for_valid_claims(
    policies: list[Policy], claims: list[Claim]
) -> None:
    all_vins = {v.vin for p in policies for v in p.vehicles}
    for claim in claims:
        if claim.claim_number > "CLM-00017":
            continue  # adversarial claims intentionally break these invariants
        assert claim.vehicle_vin in all_vins, (
            f"{claim.claim_number}: VIN {claim.vehicle_vin!r} not found in any policy"
        )


# ---------------------------------------------------------------------------
# Adversarial claims
# ---------------------------------------------------------------------------


def test_adversarial_claim_18_incident_date_outside_policy_period(
    policies: list[Policy], claims: list[Claim]
) -> None:
    policy = next(p for p in policies if p.policy_number == "POL-00001")
    claim = next(c for c in claims if c.claim_number == "CLM-00018")
    assert claim.incident.incident_date < policy.effective_date


def test_adversarial_claim_19_references_unknown_policy(
    policies: list[Policy], claims: list[Claim]
) -> None:
    claim = next(c for c in claims if c.claim_number == "CLM-00019")
    assert claim.policy_number == "POL-99999"
    assert claim.policy_number not in {p.policy_number for p in policies}


def test_adversarial_claim_20_incident_type_lacks_matching_coverage(
    policies: list[Policy], claims: list[Claim]
) -> None:
    claim = next(c for c in claims if c.claim_number == "CLM-00020")
    assert claim.incident.incident_type == IncidentType.THEFT
    policy = next(p for p in policies if p.policy_number == claim.policy_number)
    assert CoverageType.COMPREHENSIVE not in {c.coverage_type for c in policy.coverages}


# ---------------------------------------------------------------------------
# End-to-end tier distribution
# ---------------------------------------------------------------------------


def test_tier_distribution_loaded_from_real_thresholds(claims: list[Claim]) -> None:
    """Prove the seed data exercises every tier as designed, through real tier logic."""
    non_adversarial = [c for c in claims if c.claim_number <= "CLM-00017"]

    distribution: Counter[str] = Counter()
    for claim in non_adversarial:
        tier = assign_tier(claim, _THRESHOLDS)
        if tier is Tier.RED and claim.incident.injuries_reported:
            key = "red_injury"
        elif tier is Tier.RED:
            key = "red_damage"
        else:
            key = tier.value  # "green", "yellow", "black"
        distribution[key] += 1

    assert distribution["green"] == 5
    assert distribution["yellow"] == 5
    assert distribution["red_damage"] == 3
    assert distribution["red_injury"] == 2
    assert distribution["black"] == 2
