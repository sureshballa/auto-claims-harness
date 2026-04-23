"""Pure-Python payout calculations for auto-insurance claims.

No LLM calls, no MAF imports, no config imports. All functions are
stateless and depend only on the domain models passed in.
"""

from decimal import Decimal

from domain.models import Claim, Coverage, CoverageType, IncidentType, Policy


def coverage_applies(claim: Claim, policy: Policy) -> Coverage | None:
    """Return the Coverage from the policy that applies to this claim, or None.

    Liability coverage is for third-party damage and is never returned here.
    IncidentType.OTHER cannot be auto-determined and always returns None.
    """
    coverage_map: dict[CoverageType, Coverage] = {c.coverage_type: c for c in policy.coverages}

    match claim.incident.incident_type:
        case IncidentType.COLLISION:
            return coverage_map.get(CoverageType.COLLISION)
        case IncidentType.THEFT | IncidentType.VANDALISM | IncidentType.WEATHER | IncidentType.FIRE:
            return coverage_map.get(CoverageType.COMPREHENSIVE)
        case IncidentType.OTHER:
            return None
        case _:
            return None


def calculate_payout(damage_amount: Decimal, coverage: Coverage) -> Decimal:
    """Calculate the insurer payout for a given damage amount and coverage line.

    Returns max(0, min(damage_amount - deductible, limit)).
    Raises ValueError if damage_amount is negative.
    """
    if damage_amount < Decimal("0"):
        raise ValueError(f"damage_amount must be >= 0, got {damage_amount}")
    return max(Decimal("0"), min(damage_amount - coverage.deductible, coverage.limit))


def policy_active_for_claim(policy: Policy, claim: Claim) -> bool:
    """Return True if the policy was active on the date the incident occurred."""
    return policy.is_active_on(claim.incident.incident_date)
