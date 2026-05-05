"""Tests for harness/policy_engine/mock_repository.py."""

from __future__ import annotations

from domain.mock_data import load_policies
from harness.contracts import PolicyRepository
from harness.policy_engine.mock_repository import MockDataPolicyRepository


def test_satisfies_protocol_structurally() -> None:
    """MockDataPolicyRepository must satisfy PolicyRepository structurally."""
    repo = MockDataPolicyRepository()
    assert isinstance(repo, PolicyRepository)


def test_get_by_number_returns_existing_policy() -> None:
    """A policy_number that exists in mock data returns the matching Policy."""
    repo = MockDataPolicyRepository()
    known = load_policies()[0]
    result = repo.get_by_number(known.policy_number)

    assert result is not None
    assert result.policy_number == known.policy_number


def test_get_by_number_returns_none_for_missing() -> None:
    """A policy_number not in mock data returns None, not an exception."""
    repo = MockDataPolicyRepository()
    assert repo.get_by_number("POL-99999") is None


def test_get_by_number_is_idempotent() -> None:
    """The same policy_number returns an equal Policy on repeated calls."""
    repo = MockDataPolicyRepository()
    number = load_policies()[0].policy_number

    first = repo.get_by_number(number)
    second = repo.get_by_number(number)

    assert first is not None
    assert first == second


def test_repository_loads_all_policies() -> None:
    """No policies are silently dropped during indexing."""
    repo = MockDataPolicyRepository()
    all_policies = load_policies()

    for policy in all_policies:
        assert repo.get_by_number(policy.policy_number) is not None

    assert len(repo._by_number) == len(all_policies)
