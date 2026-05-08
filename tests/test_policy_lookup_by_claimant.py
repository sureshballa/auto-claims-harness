"""Tests for tools/policy_lookup_by_claimant.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.models import Coverage, CoverageType, Policy, Vehicle
from tools.policy_lookup_by_claimant import make_policy_lookup_by_claimant

_VIN = "1HGBH41JXMN109186"  # 17 chars


class _StubRepo:
    """Minimal PolicyRepository stub. Returns whatever list was set at construction."""

    def __init__(self, policies: list[Policy]) -> None:
        self._policies = policies

    def get_by_number(self, policy_number: str) -> Policy | None:
        """Not used by policy_lookup_by_claimant; satisfies PolicyRepository Protocol."""
        return None

    def find_by_claimant(self, name: str) -> list[Policy]:
        """Return the stored list regardless of the name passed."""
        return list(self._policies)


def _make_policy(policy_number: str = "POL-TEST-001") -> Policy:
    return Policy(
        policy_number=policy_number,
        policyholder_name="Jane Tester",
        policyholder_email="jane@test.example.com",
        effective_date=date(2025, 1, 1),
        expiration_date=date(2027, 12, 31),
        vehicles=[
            Vehicle(
                vin=_VIN,
                year=2020,
                make="Toyota",
                model="Camry",
                value_estimate=Decimal("24000"),
            )
        ],
        coverages=[
            Coverage(
                coverage_type=CoverageType.COLLISION,
                limit=Decimal("25000.00"),
                deductible=Decimal("500.00"),
            )
        ],
    )


def test_returns_found_true_when_repository_has_policies() -> None:
    """Tool returns found=True with count and policies list when the repository has a match."""
    policy = _make_policy()
    tool = make_policy_lookup_by_claimant(_StubRepo([policy]))
    result = tool(name="Jane Tester")

    assert result["found"] is True
    assert result["count"] == 1
    assert len(result["policies"]) == 1
    assert result["policies"][0]["policy_number"] == "POL-TEST-001"


def test_returns_found_false_when_repository_returns_empty_list() -> None:
    """Tool returns found=False with count 0 when the repository has no match."""
    tool = make_policy_lookup_by_claimant(_StubRepo([]))
    result = tool(name="Unknown Person")

    assert result["found"] is False
    assert result["name"] == "Unknown Person"
    assert result["count"] == 0
    assert "policies" not in result


def test_returns_multiple_policies_when_claimant_has_multiple() -> None:
    """Tool returns all policies when the claimant holds more than one."""
    policies = [_make_policy("POL-TEST-001"), _make_policy("POL-TEST-002")]
    tool = make_policy_lookup_by_claimant(_StubRepo(policies))
    result = tool(name="Jane Tester")

    assert result["found"] is True
    assert result["count"] == 2
    assert len(result["policies"]) == 2
    numbers = {p["policy_number"] for p in result["policies"]}
    assert numbers == {"POL-TEST-001", "POL-TEST-002"}


def test_decimal_fields_serialize_to_strings_in_returned_policies() -> None:
    """mode='json' serializes Decimal coverage amounts to strings for every policy in the list."""
    tool = make_policy_lookup_by_claimant(_StubRepo([_make_policy()]))
    result = tool(name="Jane Tester")

    coverage = result["policies"][0]["coverages"][0]
    assert coverage["limit"] == "25000.00"
    assert coverage["deductible"] == "500.00"
    assert isinstance(coverage["limit"], str)
    assert isinstance(coverage["deductible"], str)
