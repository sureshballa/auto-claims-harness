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


def test_find_by_claimant_returns_all_policies_for_known_name() -> None:
    """find_by_claimant returns every policy belonging to a claimant with multiple policies."""
    repo = MockDataPolicyRepository()
    all_policies = load_policies()

    # Derive a name with multiple policies from the seed data itself.
    counts: dict[str, int] = {}
    for p in all_policies:
        counts[p.policyholder_name] = counts.get(p.policyholder_name, 0) + 1
    name = next(n for n, c in counts.items() if c > 1)

    expected = [p for p in all_policies if p.policyholder_name == name]
    result = repo.find_by_claimant(name)

    assert len(result) == len(expected)
    assert {p.policy_number for p in result} == {p.policy_number for p in expected}


def test_find_by_claimant_is_case_insensitive() -> None:
    """Lowercase, uppercase, and mixed-case queries all return the same policies."""
    repo = MockDataPolicyRepository()
    name = load_policies()[0].policyholder_name

    lower = repo.find_by_claimant(name.lower())
    upper = repo.find_by_claimant(name.upper())
    original = repo.find_by_claimant(name)

    assert {p.policy_number for p in lower} == {p.policy_number for p in original}
    assert {p.policy_number for p in upper} == {p.policy_number for p in original}


def test_find_by_claimant_returns_empty_list_for_unknown_name() -> None:
    """A name absent from the seed data returns [], not None and not an exception."""
    repo = MockDataPolicyRepository()
    result = repo.find_by_claimant("Definitely Not A Real Policyholder Name")
    assert result == []


def test_find_by_claimant_returns_defensive_copy() -> None:
    """Mutating the returned list does not corrupt the internal index."""
    repo = MockDataPolicyRepository()
    all_policies = load_policies()
    counts: dict[str, int] = {}
    for p in all_policies:
        counts[p.policyholder_name] = counts.get(p.policyholder_name, 0) + 1
    name = next(n for n, c in counts.items() if c > 1)

    first = repo.find_by_claimant(name)
    original_len = len(first)
    first.pop()  # mutate the returned list

    second = repo.find_by_claimant(name)
    assert len(second) == original_len


def test_find_by_claimant_results_are_policies_not_just_numbers() -> None:
    """Returned items are full Policy instances, not identifiers or partial objects."""
    from domain.models import Policy

    repo = MockDataPolicyRepository()
    name = load_policies()[0].policyholder_name
    results = repo.find_by_claimant(name)

    assert len(results) >= 1
    for item in results:
        assert isinstance(item, Policy)
        assert item.policyholder_name == name
        assert len(item.coverages) >= 1
        assert len(item.vehicles) >= 1
