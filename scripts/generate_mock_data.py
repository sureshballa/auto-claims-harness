#!/usr/bin/env python3
"""Generate reproducible mock seed data for the auto-claims harness.

Usage:
    uv run python scripts/generate_mock_data.py

Outputs:
    domain/mock_data/policies.json   — 50 Policy records
    domain/mock_data/claims.json     — 20 Claim records (annotated by target tier)
"""

import json
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

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
# Static fixtures
# ---------------------------------------------------------------------------

_NAMES: list[str] = [
    "Alex Chen",
    "Jordan Patel",
    "Morgan Diaz",
    "Taylor Kim",
    "Casey Rivera",
    "Riley Thompson",
    "Avery Nguyen",
    "Quinn Okafor",
    "Skyler Mensah",
    "Jamie Kowalski",
    "Drew Herrera",
    "Reese Yamamoto",
    "Sage Abramowitz",
    "Parker Nwosu",
    "Finley Johansson",
]

_MAKES_MODELS: list[tuple[str, str]] = [
    ("Toyota", "Camry"),
    ("Honda", "Civic"),
    ("Ford", "F-150"),
    ("Tesla", "Model 3"),
    ("Chevrolet", "Silverado"),
]

_DESCRIPTIONS: dict[IncidentType, list[str]] = {
    IncidentType.COLLISION: [
        "Rear-ended at red light.",
        "Sideswiped while merging on the highway.",
        "Hit a parked car while reversing.",
        "Front-end collision at intersection.",
        "Struck guard rail on curved road.",
    ],
    IncidentType.THEFT: [
        "Vehicle stolen from parking lot overnight.",
        "Car taken from residential street.",
        "Vehicle stolen from mall parking structure.",
    ],
    IncidentType.WEATHER: [
        "Hail damage during severe storm.",
        "Tree branch fell on vehicle during windstorm.",
        "Flooded engine after flash flooding.",
    ],
    IncidentType.VANDALISM: [
        "Keyed across driver-side doors.",
        "Windows smashed and stereo removed.",
    ],
    IncidentType.FIRE: [
        "Engine fire in garage.",
        "Electrical fire while parked.",
    ],
    IncidentType.OTHER: [
        "Damage cause undetermined.",
    ],
}

_LOCATIONS: list[str] = [
    "Chicago, IL",
    "Austin, TX",
    "Phoenix, AZ",
    "Seattle, WA",
    "Denver, CO",
    "Miami, FL",
    "Portland, OR",
    "Atlanta, GA",
]

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _name_to_email(name: str) -> str:
    """Derive a deterministic .test address from a full name."""
    return f"{'.'.join(name.lower().split())}@example.test"


def _make_vin(seq: int) -> str:
    """Build a 17-char synthetic VIN from a unique sequence number (prefix + 12-digit pad)."""
    return f"1HGCM{seq:012d}"


def _rand_decimal(lo: Decimal, hi: Decimal) -> Decimal:
    """Return a random Decimal in [lo, hi] with 2-cent precision, avoiding float arithmetic."""
    lo_cents = int(lo * 100)
    hi_cents = int(hi * 100)
    return Decimal(random.randint(lo_cents, hi_cents)) / Decimal("100")


def _rand_date(start: date, end: date) -> date:
    """Return a uniformly random date in [start, end] inclusive."""
    return start + timedelta(days=random.randint(0, (end - start).days))


# ---------------------------------------------------------------------------
# Policy generation
# ---------------------------------------------------------------------------


def _make_policies(today: date) -> list[Policy]:
    """Return exactly 50 Policy records with randomised vehicles and coverages."""
    two_years_ago = today - timedelta(days=730)
    six_months_ago = today - timedelta(days=183)
    vin_seq = 1
    policies: list[Policy] = []

    for i in range(1, 51):
        name = random.choice(_NAMES)
        effective = _rand_date(two_years_ago, six_months_ago)
        expiration = effective + timedelta(days=365)

        num_vehicles = 2 if random.random() < 0.2 else 1
        vehicles: list[Vehicle] = []
        for _ in range(num_vehicles):
            make, model = random.choice(_MAKES_MODELS)
            vehicles.append(
                Vehicle(
                    vin=_make_vin(vin_seq),
                    year=random.randint(2010, 2024),
                    make=make,
                    model=model,
                    value_estimate=_rand_decimal(Decimal("8000"), Decimal("45000")),
                )
            )
            vin_seq += 1

        coverages: list[Coverage] = [
            Coverage(
                coverage_type=CoverageType.LIABILITY,
                limit=Decimal("50000"),
                deductible=Decimal("0"),
            )
        ]
        if random.random() < 0.7:
            coverages.append(
                Coverage(
                    coverage_type=CoverageType.COLLISION,
                    limit=Decimal("25000"),
                    deductible=random.choice([Decimal("500"), Decimal("1000")]),
                )
            )
        if random.random() < 0.6:
            coverages.append(
                Coverage(
                    coverage_type=CoverageType.COMPREHENSIVE,
                    limit=Decimal("20000"),
                    deductible=random.choice([Decimal("250"), Decimal("500")]),
                )
            )

        policies.append(
            Policy(
                policy_number=f"POL-{i:05d}",
                policyholder_name=name,
                policyholder_email=_name_to_email(name),
                effective_date=effective,
                expiration_date=expiration,
                vehicles=vehicles,
                coverages=coverages,
            )
        )

    return policies


# ---------------------------------------------------------------------------
# Claim helpers
# ---------------------------------------------------------------------------


def _shop_estimate(amount: Decimal) -> DamageAssessment:
    """Return a shop-estimate DamageAssessment at standard 0.85 confidence."""
    return DamageAssessment(
        assessed_amount=amount,
        assessment_source="shop_estimate",
        confidence=Decimal("0.85"),
    )


def _collision_pool(policies: list[Policy]) -> list[Policy]:
    """Return policies that carry COLLISION coverage."""
    return [
        p for p in policies if any(c.coverage_type == CoverageType.COLLISION for c in p.coverages)
    ]


def _no_comprehensive_pool(policies: list[Policy]) -> list[Policy]:
    """Return policies that do NOT carry COMPREHENSIVE coverage."""
    return [
        p
        for p in policies
        if not any(c.coverage_type == CoverageType.COMPREHENSIVE for c in p.coverages)
    ]


def _make_incident(
    policy: Policy,
    incident_type: IncidentType,
    *,
    injuries: bool = False,
    other_parties: bool = False,
) -> IncidentDetails:
    """Return an IncidentDetails with a random date inside the policy's active period."""
    return IncidentDetails(
        incident_type=incident_type,
        incident_date=_rand_date(policy.effective_date, policy.expiration_date),
        description=random.choice(_DESCRIPTIONS[incident_type]),
        location=random.choice(_LOCATIONS),
        police_report_number=None,
        injuries_reported=injuries,
        other_parties_involved=other_parties,
    )


# ---------------------------------------------------------------------------
# Claim generation
# ---------------------------------------------------------------------------


def _make_claims(policies: list[Policy], today: date) -> list[Claim]:
    """Return exactly 20 Claim records covering all target tiers and adversarial cases."""
    col_pool = _collision_pool(policies)
    no_comp = _no_comprehensive_pool(policies)
    claims: list[Claim] = []

    # CLM-00001-CLM-00005: target Green (collision, damage 100-450)
    for i in range(1, 6):
        policy = random.choice(col_pool)
        claims.append(
            Claim(
                claim_number=f"CLM-{i:05d}",
                policy_number=policy.policy_number,
                vehicle_vin=random.choice(policy.vehicles).vin,
                incident=_make_incident(policy, IncidentType.COLLISION),
                damage=_shop_estimate(_rand_decimal(Decimal("100"), Decimal("450"))),
                status=ClaimStatus.OPEN,
                created_at=today,
            )
        )

    # CLM-00006-CLM-00010: target Yellow (collision, damage 800-4500)
    for i in range(6, 11):
        policy = random.choice(col_pool)
        claims.append(
            Claim(
                claim_number=f"CLM-{i:05d}",
                policy_number=policy.policy_number,
                vehicle_vin=random.choice(policy.vehicles).vin,
                incident=_make_incident(policy, IncidentType.COLLISION),
                damage=_shop_estimate(_rand_decimal(Decimal("800"), Decimal("4500"))),
                status=ClaimStatus.OPEN,
                created_at=today,
            )
        )

    # CLM-00011-CLM-00013: target Red by damage (8000-20000)
    for i in range(11, 14):
        policy = random.choice(col_pool)
        claims.append(
            Claim(
                claim_number=f"CLM-{i:05d}",
                policy_number=policy.policy_number,
                vehicle_vin=random.choice(policy.vehicles).vin,
                incident=_make_incident(policy, IncidentType.COLLISION),
                damage=_shop_estimate(_rand_decimal(Decimal("8000"), Decimal("20000"))),
                status=ClaimStatus.OPEN,
                created_at=today,
            )
        )

    # CLM-00014-CLM-00015: target Red by injury escalation (Yellow damage + injuries_reported)
    for i in range(14, 16):
        policy = random.choice(col_pool)
        claims.append(
            Claim(
                claim_number=f"CLM-{i:05d}",
                policy_number=policy.policy_number,
                vehicle_vin=random.choice(policy.vehicles).vin,
                incident=_make_incident(policy, IncidentType.COLLISION, injuries=True),
                damage=_shop_estimate(_rand_decimal(Decimal("2000"), Decimal("4000"))),
                status=ClaimStatus.OPEN,
                created_at=today,
            )
        )

    # CLM-00016: target Black (damage 35000)
    policy = random.choice(col_pool)
    claims.append(
        Claim(
            claim_number="CLM-00016",
            policy_number=policy.policy_number,
            vehicle_vin=random.choice(policy.vehicles).vin,
            incident=_make_incident(policy, IncidentType.COLLISION),
            damage=_shop_estimate(Decimal("35000")),
            status=ClaimStatus.OPEN,
            created_at=today,
        )
    )

    # CLM-00017: target Black (damage 60000)
    policy = random.choice(col_pool)
    claims.append(
        Claim(
            claim_number="CLM-00017",
            policy_number=policy.policy_number,
            vehicle_vin=random.choice(policy.vehicles).vin,
            incident=_make_incident(policy, IncidentType.COLLISION),
            damage=_shop_estimate(Decimal("60000")),
            status=ClaimStatus.OPEN,
            created_at=today,
        )
    )

    # CLM-00018: adversarial — incident 2 years before POL-00001's effective date
    pol_00001 = next(p for p in policies if p.policy_number == "POL-00001")
    pre_policy_date = pol_00001.effective_date - timedelta(days=730)
    claims.append(
        Claim(
            claim_number="CLM-00018",
            policy_number="POL-00001",
            vehicle_vin=random.choice(pol_00001.vehicles).vin,
            incident=IncidentDetails(
                incident_type=IncidentType.COLLISION,
                incident_date=pre_policy_date,
                description=random.choice(_DESCRIPTIONS[IncidentType.COLLISION]),
                location=random.choice(_LOCATIONS),
                police_report_number=None,
                injuries_reported=False,
                other_parties_involved=False,
            ),
            damage=_shop_estimate(Decimal("1500")),
            status=ClaimStatus.OPEN,
            created_at=today,
        )
    )

    # CLM-00019: adversarial — references policy POL-99999 which does not exist
    claims.append(
        Claim(
            claim_number="CLM-00019",
            policy_number="POL-99999",
            vehicle_vin="1HGCM000000000000",
            incident=IncidentDetails(
                incident_type=IncidentType.COLLISION,
                incident_date=today - timedelta(days=30),
                description=random.choice(_DESCRIPTIONS[IncidentType.COLLISION]),
                location=random.choice(_LOCATIONS),
                police_report_number=None,
                injuries_reported=False,
                other_parties_involved=False,
            ),
            damage=_shop_estimate(Decimal("2000")),
            status=ClaimStatus.OPEN,
            created_at=today,
        )
    )

    # CLM-00020: adversarial — THEFT against a policy without COMPREHENSIVE coverage
    policy = random.choice(no_comp)
    claims.append(
        Claim(
            claim_number="CLM-00020",
            policy_number=policy.policy_number,
            vehicle_vin=random.choice(policy.vehicles).vin,
            incident=_make_incident(policy, IncidentType.THEFT),
            damage=None,
            status=ClaimStatus.OPEN,
            created_at=today,
        )
    )

    return claims


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate policies.json and claims.json, then print a summary."""
    random.seed(42)
    today = date.today()

    policies = _make_policies(today)
    claims = _make_claims(policies, today)

    out_dir = Path(__file__).resolve().parent.parent / "domain" / "mock_data"
    out_dir.mkdir(parents=True, exist_ok=True)
    policies_path = out_dir / "policies.json"
    claims_path = out_dir / "claims.json"

    policies_path.write_text(
        json.dumps([json.loads(p.model_dump_json()) for p in policies], indent=2)
    )
    claims_path.write_text(json.dumps([json.loads(c.model_dump_json()) for c in claims], indent=2))

    print(f"Policies    : {len(policies)}  →  {policies_path}")
    print(f"Claims      : {len(claims)}  →  {claims_path}")
    print("  Green       CLM-00001-CLM-00005  :  5")
    print("  Yellow      CLM-00006-CLM-00010  :  5")
    print("  Red         CLM-00011-CLM-00015  :  5  (3 by damage, 2 by injury escalation)")
    print("  Black       CLM-00016-CLM-00017  :  2")
    print("  Adversarial CLM-00018-CLM-00020  :  3  (lapsed date, ghost policy, no coverage)")


if __name__ == "__main__":
    main()
