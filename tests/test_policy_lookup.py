"""Tests for tools/policy_lookup.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.models import Coverage, CoverageType, Policy, Vehicle
from tools.policy_lookup import make_policy_lookup

_VIN = "1HGBH41JXMN109186"  # 17 chars


class _StubRepo:
    """Minimal PolicyRepository stub. Returns whatever was set at construction."""

    def __init__(self, policy: Policy | None) -> None:
        self._policy = policy

    def get_by_number(self, policy_number: str) -> Policy | None:
        """Return the stored policy regardless of the number passed."""
        return self._policy


def _make_policy() -> Policy:
    return Policy(
        policy_number="POL-TEST-001",
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


def test_returns_found_true_with_policy_data_when_repository_has_policy() -> None:
    """Tool returns found=True and full policy data when the repository has the policy."""
    policy = _make_policy()
    tool = make_policy_lookup(_StubRepo(policy))
    result = tool(policy_number="POL-TEST-001")

    assert result["found"] is True
    assert "policy" in result
    assert result["policy"]["policy_number"] == "POL-TEST-001"
    assert "found" not in result["policy"]


def test_returns_found_false_when_repository_returns_none() -> None:
    """Tool returns found=False with the queried number when the repository has no match."""
    tool = make_policy_lookup(_StubRepo(None))
    result = tool(policy_number="POL-MISSING")

    assert result["found"] is False
    assert result["policy_number"] == "POL-MISSING"
    assert "policy" not in result


def test_decimal_fields_serialize_to_strings_in_returned_dict() -> None:
    """mode='json' serializes Decimal coverage amounts to strings, not floats."""
    tool = make_policy_lookup(_StubRepo(_make_policy()))
    result = tool(policy_number="POL-TEST-001")

    coverage = result["policy"]["coverages"][0]
    assert coverage["limit"] == "25000.00"
    assert coverage["deductible"] == "500.00"
    assert isinstance(coverage["limit"], str)
    assert isinstance(coverage["deductible"], str)


def test_date_fields_serialize_to_strings_in_returned_dict() -> None:
    """mode='json' serializes date fields to ISO-format strings, not date objects."""
    tool = make_policy_lookup(_StubRepo(_make_policy()))
    result = tool(policy_number="POL-TEST-001")

    assert result["policy"]["effective_date"] == "2025-01-01"
    assert result["policy"]["expiration_date"] == "2027-12-31"
    assert isinstance(result["policy"]["effective_date"], str)
    assert isinstance(result["policy"]["expiration_date"], str)
